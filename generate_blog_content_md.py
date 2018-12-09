#!/usr/bin/python
# -*- coding: UTF-8 -*-
import sys
import generate_articles_sql as ga
import subprocess

reload(sys)
sys.setdefaultencoding('utf8')


def write_to_clipboard(output):
    process = subprocess.Popen(
        'pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE)
    process.communicate(output.encode('utf-8'))


def main():
    args = sys.argv
    file_name = "redis-trs-modules-intro"
    files_dict = ga.get_files_dict()
    configs_dict = ga.get_configs_dict(files_dict)
    c_file = files_dict[file_name]
    print c_file
    print configs_dict[file_name]["title"]
    content = None
    with open(c_file, 'r') as f:
        content = f.read()
        content = ga.turn_image_link(content, "http://s.charpty.com/")
        # print "\n"
        # print content
        # 拷贝到osx剪切板
        write_to_clipboard(content)
    with open("current_md_content.md", "wb") as f:
        f.write(content)
        f.close


if __name__ == '__main__':
    main()
