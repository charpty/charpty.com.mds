#!/usr/bin/python
# -*- coding: UTF-8 -*-
import sys
import generate_articles_sql as ga

reload(sys)
sys.setdefaultencoding('utf8')


def main():
    args = sys.argv
    file_name = "write-red-black-tree"
    files_dict = ga.get_files_dict()
    configs_dict = ga.get_configs_dict(files_dict)
    c_file = files_dict[file_name]
    print c_file
    print configs_dict[file_name]["title"]
    content = None
    with open(c_file, 'r') as f:
        content = f.read()
        content = ga.turn_image_link(content, "http://s.charpty.com/")
        # print content
    with open("current_md_content.md", "wb") as f:
        f.write(content)
        f.close


if __name__ == '__main__':
    main()
