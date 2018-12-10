#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import os
import json
import utils
import datetime
import ntpath
import subprocess

reload(sys)
sys.setdefaultencoding('utf8')

meta_sql_format = "REPLACE INTO `ARTICLE_META` (`NAME`,`TYPE`,`TITLE`,`TAG`,`SUMMARY`,`COVER_IMAGE`," \
                  "`GROUP_NAME`,`CREATOR`,`CREATION_DATE`,`MODIFICATION_DATE`,`DISPLAY_ORDER`,`WORD_COUNT`" \
                  ") VALUES ('%s',%d,'%s','%s','%s','%s','%s','%s','%s','%s',%d,%d);"
content_sql_format = "REPLACE INTO `ARTICLE_CONTENT` (`NAME`,`CONTENT`) VALUES ('%s','%s');"

key_config_file_path = "file_path"
pattern_link_start = "["
pattern_link_end = "]("
pattern_link_next_start = ")"
default_resource_host = "http://s.charpty.com/"


def check_file(filename):
    if filename.endswith(".md"):
        return True
    if filename.endswith(".json"):
        return True
    return False


def clean_suffix(file_name):
    return file_name[:str(file_name).find(".")]


def get_file_name(path):
    return ntpath.basename(path)


def write_to_clipboard(output):
    process = subprocess.Popen(
        'pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE)
    process.communicate(output.encode('utf-8'))


def get_files_dict(root_dir="articles"):
    files_dict = {}
    for root, dirs, files in os.walk(root_dir):
        for name in files:
            if check_file(name):
                files_dict[clean_suffix(name)] = os.path.join(root, name)
    return files_dict


def read_config(file_path, configs_dict):
    with open(file_path, 'r') as config_f:
        configs = json.load(config_f)
        for c in configs:
            if "name" not in c:
                raise ValueError("config should have property 'name', file: %s" % file_path)
            name = c["name"]
            if "imageHost" not in c:
                c["imageHost"] = default_resource_host
            if name in configs_dict:
                raise ValueError("config name '%s' already in dict: first: %s, current: %s"
                                 % (name, configs_dict[name][key_config_file_path], file_path))
            c[key_config_file_path] = file_path
            configs_dict[name] = c


def get_configs_dict(files_dict):
    configs_dict = {}
    for path in sorted(files_dict.values()):
        if not path.endswith("config.json"):
            continue
        read_config(path, configs_dict)
    return configs_dict


def turn_image_link(text, image_host):
    start = 0
    len_start = len(pattern_link_start)
    len_end = len(pattern_link_end)
    endswith_dash = default_resource_host.endswith("/");
    while (start + 1) < len(text):
        index_start = text.find(pattern_link_start, start)
        if index_start < 0:
            break
        index_end = text.find(pattern_link_end, index_start + len_start + 1)
        desc = text[index_start + len_start:index_end]
        index_next = text.find(pattern_link_next_start, index_end + len_end + 1)
        url = text[index_end + len_end:index_next]
        valid_url = 255 > len(url) > 5 and "[" not in url and "]" not in url and "(" not in url and ")" not in url
        valid_desc = len(desc) < 30 and "[" not in desc and "]" not in desc and "(" not in desc and ")" not in desc
        if valid_desc and valid_url:
            d_len = 0
            if endswith_dash and url.startswith("/"):
                d_len = 1
            text = text[:index_end + len_end] + image_host + text[index_end + len_end + d_len:]
            # just make start > index_start
            start = index_next + 1
        else:
            start = index_start + 1
    return text


def escape_sql(text):
    # for line ending with '\'
    text = text.replace('\\\n', '\\n')
    # for \r\n
    text = text.replace('\\r\\n', '\\\\r\\\\n')
    # for '\n'
    text = text.replace('\'\\n\'', '\'\\\\n\'')
    # for '\r'
    text = text.replace('\'\\r\'', '\'\\\\r\'')
    # for \u
    text = text.replace('\\u', '\\\\u')

    text = text.replace('\n', '\\n')
    text = text.replace('\'', '\\\'')
    text = text.replace('\"', '\\\"')
    return text


def clean_md_content(text, image_host):
    text = escape_sql(text)
    text = turn_image_link(text, image_host)
    return text


def check_config(config):
    if "title" not in config:
        return False
    if "tags" not in config:
        return False
    if "summary" not in config:
        return False
    if "coverImage" not in config:
        return False
    if "groupName" not in config:
        return False
    if "creator" not in config:
        return False
    if "creationDate" not in config:
        return False
    if "modificationDate" not in config:
        return False
    if "displayOrder" not in config:
        return False
    return True


def less_than(date1, date2):
    d1 = datetime.datetime.strptime(date1, '%Y-%m-%d %H:%M:%S')
    d2 = datetime.datetime.strptime(date2, '%Y-%m-%d %H:%M:%S')
    return d1 < d2


def get_config_list(configs_dict):
    config_list = []
    # insert sort
    for key in configs_dict.keys():
        config = configs_dict.get(key)
        added = False
        for i, item in enumerate(config_list):
            if less_than(config["modificationDate"], item["modificationDate"]):
                config_list.insert(i, config)
                added = True
                break
        if not added:
            config_list.append(config)
    return config_list


def generate_sql_list(files_dict, configs_dict):
    sql_list = []
    modification_dates = []
    generated_articles = []
    md_files = []

    config_list = get_config_list(configs_dict)
    for config in config_list:
        md_file = files_dict.get(config["name"])
        if md_file is None:
            utils.log_warn("can not find file for '%s'" % config["name"])
            continue
        if not md_file.endswith(".md"):
            continue
        name = clean_suffix(get_file_name(md_file))
        md_files.append(name)
        with open(md_file, 'r') as mdFile:
            if not check_config(config):
                utils.log_warn("config file is invalid: name=%s, file_path=%s" % (name, config[key_config_file_path]))
                continue
            type_ = 10
            if "type" in config:
                type_ = config["type"]
            title_ = config["title"]
            tags_ = config["tags"]
            summary_ = config["summary"]
            cover_image_ = config["coverImage"]
            content = clean_md_content(mdFile.read(), config["imageHost"])
            group_name_ = config["groupName"]
            creator_ = config["creator"]
            creation_date_ = config["creationDate"]
            modification_date_ = config["modificationDate"]
            display_order_ = config["displayOrder"]
            word_count_ = len(content)
            meta_sql = meta_sql_format % (
                name, type_, title_, tags_, summary_, cover_image_,
                group_name_, creator_,
                creation_date_, modification_date_, display_order_, word_count_)
            content_sql = content_sql_format % (name, content)
            generated_articles.append("name = %-45s title = %s" % (name, title_))
            modification_dates.append(modification_date_)
            sql_list.append(meta_sql)
            sql_list.append(content_sql)

    return sql_list, modification_dates, generated_articles, md_files


def print_generated_info(files_dict, configs_dict, generated_articles, md_files):
    total_file_size = len(files_dict)
    md_file_size = len(md_files)
    config_file_size = len(configs_dict)
    final_sql_size = len(generated_articles)
    summary = "total file is %s, markdown file is %s, final generated sql is %s, configs is %s" \
              % (total_file_size, md_file_size, utils.be_success_green(final_sql_size),
                 utils.be_success_green(config_file_size))
    print summary
    print " ## There is the details:"
    for info in generated_articles:
        print "  " + info


def output_result_sql(sql_list):
    size = len(sql_list)
    to_clipboard = ""
    last_index = size - 2
    for i in range(size):
        if i % 2 == 0:
            print
        if i >= last_index:
            to_clipboard = to_clipboard + '\n' + sql_list[i]
        print sql_list[i]
    write_to_clipboard(to_clipboard)


def main():
    files_dict = get_files_dict()
    configs_dict = get_configs_dict(files_dict)
    sql_list, modification_dates, generated_articles, md_files = generate_sql_list(files_dict, configs_dict)
    print_generated_info(files_dict, configs_dict, generated_articles, md_files)
    print("############################################################################################")
    print("*************************************RESULT SQL*********************************************")
    print("############################################################################################")
    print
    output_result_sql(sql_list)


if __name__ == '__main__':
    main()
