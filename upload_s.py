#!/usr/bin/python
# -*- coding: UTF-8 -*-

import oss2
import sys
import json
import utils

reload(sys)
sys.setdefaultencoding('utf8')

KEY_AK = "ak"
KEY_SK = "sk"
KEY_END_POINT = "endPoint"
KEY_BUCKET = "bucket"
KEY_CLEAN_BUCKET = "cleanBucket"


def get_oss_config(file_path="ali-oss.pwd"):
    with open(file_path, "r") as f:
        config = json.load(f)
        if KEY_AK not in config:
            raise ValueError("config file %s should contains key '%s'" % (file_path, KEY_AK))
        if KEY_SK not in config:
            raise ValueError("config file %s should contains key '%s'" % (file_path, KEY_SK))
        if KEY_END_POINT not in config:
            raise ValueError("config file %s should contains key '%s'" % (file_path, KEY_END_POINT))
        if KEY_BUCKET not in config:
            raise ValueError("config file %s should contains key '%s'" % (file_path, KEY_BUCKET))
        if KEY_CLEAN_BUCKET not in config:
            utils.log_warn(utils.be_warning_yellow("config file %s not set %s, use default False"
                                                   % (file_path, KEY_CLEAN_BUCKET)))
            config[KEY_CLEAN_BUCKET] = False
        return config


def get_oss_bucket_handler(config):
    auth = oss2.Auth(config[KEY_AK], config[KEY_SK])
    bucket = oss2.Bucket(auth, config[KEY_END_POINT], config[KEY_BUCKET])
    return bucket


def upload_s_file(bucket_handler, file_name):
    with open(file_name, "r") as fd:
        bucket_handler.put_object("s/" + file_name, fd)
        print "%s %s" % (utils.be_success_green("success upload file: "), file_name)


def main():
    if len(sys.argv) != 2:
        raise ValueError("you can only set one input: upload file name")
    file_name = sys.argv[1]
    config = get_oss_config()
    bucket_handler = get_oss_bucket_handler(config)
    upload_s_file(bucket_handler, file_name)


if __name__ == '__main__':
    main()
