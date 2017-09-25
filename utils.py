def be_success_green(text):
    return "\033[92m%s\033[0m" % str(text)


def be_warning_yellow(text):
    return "\033[93m%s\033[0m" % str(text)


def log_warn(message):
    print "[WARN] %s" % message
