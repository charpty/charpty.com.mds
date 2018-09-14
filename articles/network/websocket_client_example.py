# -*- coding: utf-8 -*-

import sys
import socket
import time
import binascii
import struct
import threading
import zlib

reload(sys)
sys.setdefaultencoding('utf-8')

# 一个普通的HTTP请求，带上Host以及升级为WebSocket连接必要的几个header
# 在测试中没有必要启用gzip压缩
# "Sec-WebSocket-Extensions: permessage-deflate; client_max_window_bits=15\r\n"
UPGRADE_REQUEST = "GET /gs-guide-websocket/382/4ekj1wpx/websocket HTTP/1.1\r\n" \
                  "Host: localhost:8080\r\n" \
                  "Sec-WebSocket-Key: Wge6UZ+MyDoA1swg1UaZqg==\r\n" \
                  "Sec-WebSocket-Version: 13\r\n" \
                  "Upgrade: websocket\r\n" \
                  "Connection: Upgrade\r\n" \
                  "\r\n"

# 告诉服务器我们支持的版本有1.2、1.1、1.0，服务器一般会选最高可支持版本
CONNECT_COMMAND = "[\"CONNECT\\n" \
                  "accept-version:1.2,1.1,1.0\\n" \
                  "heart-beat:1000,1000\\n" \
                  "\\n\u0000\"]"

# 我们订阅/topic/greetings，Spring WebSocket示例中会往这个频道发送消息
SUBSCRIBE_COMMAND = "[\"SUBSCRIBE\\n" \
                    "id:0\\n" \
                    "destination:/topic/greetings\\n" \
                    "\\n\u0000\"]"

# Spring WebSocket示例中往这个路径发送name会返回hello, name
CHAT_COMMAND_FORMAT = "[\"SEND\\n" \
                      "destination:/app/hello\\n" \
                      "content-length:%s\\n\\n" \
                      "{\\\"name\\\":\\\"%s\\\"}\u0000\"]"

MY_MASK = [0x00, 0x00, 0x00, 0x00]


# 使用-Dorg.apache.tomcat.websocket.DISABLE_BUILTIN_EXTENSIONS=true可以让基于tomcat ws container的容器避免压缩
# 解压gzip压缩的业务payload
def decompress_gzip_payload(payload):
    do = zlib.decompressobj(-zlib.MAX_WBITS)
    try:
        data = do.decompress(payload)
        return data
    except BaseException as e:
        print "error payload: " + binascii.hexlify(payload)
        raise e


def log_payload(payload):
    if payload is None:
        return
    if len(payload) < 5:
        print "receive heart check: " + payload
        return
    # print "receive hex: " + binascii.hexlify(payload)
    print "*******receive message start*******"
    # 简单处理，先清理掉"[ 和结束符
    payload = payload[3:-8]
    for line in payload.split('\\n'):
        print line
    print "*******receive message end********"


def receive_loop(sk, buf):
    # websocket是T-L-V格式的消息，大概是第一个字节表示类型，第二个字节表示长度，后续为具体数据
    buf = buf + sk.recv(4096)
    # 第一个byte一般都为1100 0001，表示fin结束块，rsv1=使用zlib压缩，文本消息
    # 高位1表示fin结束块，第二高位位1表示zlib压缩（spring自定义），末位为消息类型，一般都是1表示文本消息
    if buf is None:
        time.sleep(1)
        return
    flags = ord(buf[0])
    fin = flags >> 7
    # 不是结束块，那就还没读完
    if fin == 0:
        return
    # 是否使用gzip压缩
    is_compress = rsv1 = (flags & 0x40) >> 6
    # rsv2、rsv3目前都是保留使用
    # rsv2 = (flags & 0x20) >> 5
    # rsv3 = (flags & 0x10) >> 4
    mask_payload_len = ord(buf[1])
    # 是否使用掩埋异或，从客户端送过去消息是必须使用mask的，服务端发给客户端则不需要
    mask = mask_payload_len >> 7
    # 我们送过去是要求不mask的，所以这里不判断mask了，mask=0，mask_key为空，所以这里就不用取4位mask_key了
    payload_len = mask_payload_len & 0x7F
    # payload_len小于126的为实际长度，等于126时代表后两个byte才是真实长度，等于127代表后八哥byte才是真实长度
    payload_start = 0
    if payload_len < 126:
        payload_start = 2
    elif payload_len == 126:
        len_s = buf[2:4]
        # 处理字节序为大端字节序
        payload_len = struct.unpack('>H', bytes(len_s))[0]
        payload_start = 4
    elif payload_len == 127:
        len_s = buf[2:10]
        payload_len = struct.unpack('>Q', bytes(len_s))[0]
        payload_start = 10
    # payload还没读完整
    if len(buf) < payload_start + payload_len:
        return
    payload = buf[payload_start:(payload_start + payload_len)]
    # 大端字节序处理，不处理也可，在Spring WebSocket中已处理
    payload = struct.unpack('>' + str(payload_len) + 's', payload)[0]
    buf = buf[(payload_start + payload_len):]
    # 需要解压的时候，我们在建立WebSocket时已经指定了不需要解压，这里不会走到
    if is_compress == 1:
        payload = decompress_gzip_payload(payload)
    log_payload(payload)


# websocket天生异步，用于🉑️🉑️接收消息的线程action，java中的runnable，从建立websocket子协议开始
def receive_action(sk):
    buf = ""
    while True:
        receive_loop(sk, buf)


def mask_payload(payload):
    mask_index = 0
    result = ""
    for c in payload:
        mask = MY_MASK[mask_index] & 0xFF
        c_int = ord(c)
        after_mask = (mask ^ c_int)
        result = result + chr(after_mask)
        mask_index = mask_index + 1
        if mask_index == 3:
            mask_index = 0
    return result


def make_frame(payload):
    # 我们构造时都让长度小于65536
    p_len = len(payload)
    if p_len < 126:
        # 第二字节后7位就是表示payload长度
        mask_p_len = p_len | 0x80
        data_format = 'B' + 'B' + 'BBBB' + str(p_len) + 's'
        # 需要了解下python的struct模块
        frame = struct.pack(data_format, 129, mask_p_len, MY_MASK[0], MY_MASK[1], MY_MASK[2], MY_MASK[3], payload)
    elif p_len < 65536:
        # 之后的两个字节才是长度
        # mask_p_len = ((126 | 0x80) << 16) + p_len
        mask_flag = 126
        data_format = 'B' + 'BH' + 'BBBB' + str(len(payload)) + 's'
        frame = struct.pack(data_format, 129, mask_flag, p_len, MY_MASK[0], MY_MASK[1], MY_MASK[2], MY_MASK[3], payload)
    else:
        raise ValueError("这只是测试请不要发过长的内容")

    return frame


# 1、第一个8位：1000 0001 代表发送文本消息，且是结束块
# 2、第二个8位：1X，X为负载数据的长度，无扩展数据情况下即指业务payload的长度，1代表该文本已经过mask处理，客户端送数据必须mask
# 3、接下来的32位：随机的4字节掩码，我们就全部使用0好了
# 4、业务数据
def make_command(payload):
    payload = mask_payload(payload)
    frame = make_frame(payload)
    return frame


def make_chat_command(name):
    chat_command = CHAT_COMMAND_FORMAT % ((11 + len(name)), name)
    final_command = make_command(chat_command)
    return final_command


# UPGRADE连接 -> 协商协议版本号 -> 启动接收线程 -> 订阅频道 -> 发送消息
def main():
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.connect(('localhost', 8080))

    # 首先是建立连接，通过UPGRADE请求将"HTTP连接"升级为"WebSocket连接"
    sk.send(UPGRADE_REQUEST)
    time.sleep(1)
    # 正常升级连接则返回101状态码
    print "UPGRADE_REQUEST: " + sk.recv(4096)

    # WebSocket的connect，双方协商该使用的WebSocket协议版本号，同时约定心跳策略
    command = make_command(CONNECT_COMMAND)
    sk.send(command)

    # 启动接收消息线程
    t = threading.Thread(target=receive_action, args=(sk,))
    t.setName("socket receive")
    t.start()

    # 订阅感兴趣的频道
    command = make_command(SUBSCRIBE_COMMAND)
    sk.send(command)

    # 发送消息
    command = make_chat_command("jack")
    sk.send(command)

    while True:
        name = raw_input("what's your name?\r\n")
        command = make_chat_command(name)
        sk.send(command)

    t.join()


if __name__ == '__main__':
    main()
