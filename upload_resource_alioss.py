#!/usr/bin/python
# -*- coding: UTF-8 -*-

import oss2
import sys
import json
import os
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


def check_file_suffix(filename, suffix):
    if filename is None:
        return False
    for s in suffix:
        if filename.endswith(s):
            return True
    return False
    if filename.endswith(".png"):
        return True
    if filename.endswith(".jpg"):
        return True
    if filename.endswith(".bmp"):
        return True
    if filename.endswith(".gif"):
        return True
    return False


def get_file_list(root_dir, suffix=[]):
    files_list = []
    for root, dirs, files in os.walk(root_dir):
        for name in files:
            if check_file_suffix(name, suffix):
                files_list.append(os.path.join(root, name))
    return files_list


def get_oss_bucket_handler(config):
    auth = oss2.Auth(config[KEY_AK], config[KEY_SK])
    bucket = oss2.Bucket(auth, config[KEY_END_POINT], config[KEY_BUCKET])
    return bucket


def upload_files_dir(bucket_handler, files_list):
    for filename in files_list:
        with open(filename, "r") as fd:
            bucket_handler.put_object(filename, fd)
            print "%s %s" % (utils.be_success_green("success upload file: "), filename)


def print_files(files_list):
    print "total file size is %s" % utils.be_success_green(len(files_list))


def upload_resource(root_dir, suffix=[]):
    config = get_oss_config()
    bucket_handler = get_oss_bucket_handler(config)
    files_list = get_file_list(root_dir, suffix)
    print "############################################################################"
    print "UPLOAD DIR: " + root_dir
    print_files(files_list)
    upload_files_dir(bucket_handler, files_list)
    print "############################################################################"


def main():
    upload_resource("images", ['.png', '.bmp', '.jpg', '.gif'])
    upload_resource("codes", ['.py', '.java', '.c', '.cpp', '.lua', '.go'])


if __name__ == '__main__':
    main()
