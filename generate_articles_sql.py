#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import os
import json

reload(sys)
sys.setdefaultencoding('utf8')

files_dict = {}
for root, dirs, files in os.walk("articles"):
    for name in files:
        files_dict[str(name)] = os.path.join(root, name)

configs_dict = {}
with open("articles_config.json", 'r') as config_f:
    configs = json.load(config_f)
    for c in configs:
        configs_dict[c["name"]] = c

sql_list = [];

sql_head = "INSERT INTO `ARTICLE` (`NAME`,`TITLE`,`TAG`,`SUMMARY`,`COVER_IMAGE`,`CONTENT`," \
           "`GROUP_NAME`,`CREATOR`,`CREATION_DATE`,`MODIFICATION_DATE`,`DISPLAY_ORDER`" \
           ") VALUES (";

sql_template = "%s '%s','%s','%s','%s','%s','%s','%s','%s','%s','%s',%d )"

for key in sorted(files_dict.keys()):
    if not key.endswith(".md"):
        raise ValueError(key);
    name = key[:-3]
    if configs_dict.has_key(name):
        config = configs_dict[name]
        with open(files_dict.get(key), 'r') as mdFile:
            sql = sql_template % (
                sql_head, name, config["title"], config["tags"], config["summary"], config["coverImage"],
                mdFile.read().replace('\n','\\n'), config["groupName"], config["creator"], config["creationDate"],
                config["modificationDate"], config["displayOrder"])
            sql_list.append(sql)

for s in sql_list:
    print s
