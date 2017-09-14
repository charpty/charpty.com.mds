> 笔者博客地址：https://charpty.com

在开发Nginx模块或者遇到难以解决的Nginx配置问题时，不得不通过调试手段来找出问题所在，本文通过在Linux系统上使用gdb工具来演示如何调试运行中的Nginx进程，本文只关心Nginx的实际执行者--worker进程。


###（1）编译Nginx
首先你需要编译出带有调试信息的可执行文件和.o文件。
获得Nginx源码之后，通过我们熟悉的```configure```命令指定稍后make时需带有debug信息。
```shell
./configure --with-debug
```
之后直接调用相应命令编译Nginx源码即可
```shell
make
```
此时，在源码录下生成了一个objs目录，该目录下包含了带有调试信息的可执行文件和.o文件，是我们调试的关键，我们稍后的调试过程都将在这个目录下进行。

###（2）配置和启动Nginx
这里可以大家需要根据自己遇到的问题来配置自己的nginx.conf，在源码目录的conf文件夹下提供了默认的nginx.conf，由于本文只是一个示例，我们就采用Nginx的静态文件模块（```ngx_http_static_module```）来进行调试，也就是默认的nginx.conf中指定的:
```shell
    location / {
        root   html;
        index  index.html index.htm;
    }
```
这样的话，我们不需要这个配置文件进行任何改动，直接启动Nginx并指定这个Nginx提供的默认配置文件即可。

还有一点需要特别说明下，这个默认的配置文件中，也指定了worker进程的数量是1，这样无形中方便了我们进行调试
```
worker_processes  1;
```

启动方式也很方便，进入到我们刚才编译出来的objs目录下，其中有一个名为 ```nginx```的可执行文件
```shell
cd objs
# 这里需要指定一下源码中默认提供的nginx.conf的绝对路径
./nginx -c /root/nginx-1.9.9/conf/nginx.conf
```
通过```-c```选项指定配置文件之后，顺利启动了Nginx，可以查看到Nginx进程已顺利运行
```shell
ps -ef | grep nginx
```

###（3）使gdb能够调试nginx进程

首先当然是启动gdb
gdb启动有许多的模式，为了演示方便，我们使用最为直观的调试方式。
```shell
# -q: 静默模式，不显示版本信息的杂项
# -tui: 可以显示源码界面，即屏幕上方一个长期'l'指令
# 该命令应该在objs目录下执行，这样gdb才能找到源码信息
gdb -q -tui
```
*说明： -tui选项只是为了方便，如果不习惯则直接使用```gdb```命令即可，对后续的讲解无影响。

然后你需要使用gdb的```attach```命令来依附Nginx的worker进程，首先需要获取Nginx worker进程的pid
```
[root@wind4app objs]# ps -ef | grep nginx
root     25733     1  0 21:03 ?        00:00:00 nginx: master process ./nginx -c nginx.conf
nobody   25734 25733  0 21:03 ?        00:00:00 nginx: worker process
```
我们看到Nginx worker进程的pid为```25734```

使用gdb attach命令
```
(gdb) attach 25734
```
此时你已经成功依附Nginx worker进程，可以开始真正的调试了。


###（4）开始gdb调试
现在，我们可以开始真正的调试，整套流程下来很简单，熟悉了之后非常的方便。
现在，我们在想要进行调试的静态文件模块，即```ngx_http_static_ module```处打一个断点，一般来说我们都打在handler函数处，运行期间出现问题的话，大多都是handler函数内含有Bug
```
(gdb) b ngx_http_static_handler
(gdb) c
```

通过```c```选项使进程继续运行，此时一旦有访问发生，就会触发我们的断点。

此时我们可以在浏览器中请求我们的服务器地址，或者通过```curl```命令等方式来触发我们的断点，然后通过灵活的gdb命令对Nginx模块进行调试。