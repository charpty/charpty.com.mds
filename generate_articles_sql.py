#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import os
import json

reload(sys)
sys.setdefaultencoding('utf8')

sql_head = "INSERT INTO `ARTICLE` (`NAME`,`TITLE`,`TAG`,`SUMMARY`,`COVER_IMAGE`,`CONTENT`," \
           "`GROUP_NAME`,`CREATOR`,`CREATION_DATE`,`MODIFICATION_DATE`,`DISPLAY_ORDER`" \
           ") VALUES (";
article_sql_format = "%s '%s','%s','%s','%s','%s','%s','%s','%s','%s','%s',%d );"


def get_files_dict(root_dir="articles"):
    files_dict = {}
    for root, dirs, files in os.walk(root_dir):
        for name in files:
            files_dict[str(name)] = os.path.join(root, name)
    return files_dict


def get_configs_dict(config_file_name="articles_config.json"):
    configs_dict = {}
    with open("articles_config.json", 'r') as config_f:
        configs = json.load(config_f)
    for c in configs:
        configs_dict[c["name"]] = c
    return configs_dict


def clean_md_content(text):
    text = text.replace('\n', '\\n')
    text = text.replace('\'', '\\')
    return text;


def generate_sql_list(files_dict, configs_dict):
    sql_list = []
    for key in sorted(files_dict.keys()):
        if not key.endswith(".md"):
            raise ValueError(key);
        name = key[:-3]
        if not configs_dict.has_key(name):
            continue;
        config = configs_dict[name]
        with open(files_dict.get(key), 'r') as mdFile:
            title_ = config["title"]
            tags_ = config["tags"]
            summary_ = config["summary"]
            image_ = config["coverImage"]
            group_name_ = config["groupName"]
            creator_ = config["creator"]
            creation_date_ = config["creationDate"]
            modification_date_ = config["modificationDate"]
            display_order_ = config["displayOrder"]
            sql = article_sql_format % (
                sql_head, name, title_, tags_, summary_, image_,
                clean_md_content(mdFile.read()), group_name_, creator_,
                creation_date_,
                modification_date_, display_order_)
            sql_list.append(sql)
    return sql_list


def print_result_sql(sql_list):
    for s in sql_list:
        print s


def main():
    files_dict = get_files_dict()
    configs_dict = get_configs_dict()
    sql_list = generate_sql_list(files_dict, configs_dict)
    print_result_sql(sql_list)


if __name__ == '__main__':
    main()
