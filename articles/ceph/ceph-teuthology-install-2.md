ceph自动化测试环境teuthology的安装部署具体步骤

再次强调，本文所述均建立在Ubuntu14.0LTS系统之上，这是一个非常普通的系统，也是ceph官方推荐使用的。
本文中所克隆的源，有ceph官方的地址，也有H3C的地址，大家都可以自己选择，并无好坏之分，只是个参考。
本文从简到难，逐层安装，没搞懂的就搜索下，一步步装，不要跳着查看，那样反而会给自己造成麻烦，如果有什么概念上的问题，请参看上一篇文章。

> 关于我们：https://charpty.com <br>
>          https://github.com/charpty <br>
>          charpty@google.com

##paddles的安装部署
你也可以按照官方教程进行安装，还是比较简单的。

https://github.com/ceph/paddles


前提：请安装好Ubuntu系统，在虚拟机上和物理机上均可，机器要可以上网，配置好apt-get源，使用163的源，或者sohu的都可以。

（1）按照系统级别依赖
配置好apt-get的源之后，通过执行简单命令即可安装所有依赖
```shell
apt-get install python-dev python-virtualenv postgresql postgresql-contrib postgresql-server-dev-all supervisor

# 如果你的机器没有安装一些我们所需要的基本工具，我并没有办法一一陈述
# 后续碰到了，你可以自行安装，我只能大概提到一些
# git，用于拉取代码
apt-get install git
# python环境，一般默认自带，没有的话可以搜索下安装Python
# pip easy_install，这都是Python中的模块，可自行搜索安装，很简单
```
(2)安装并配置postgresql数据库
这里我们安装9.3版本，该版本稳定成熟。
```shell
# 非常方便的安装方式
apt-get install postgresql-9.3
# 安装完成之后，会默认的创建一个用户postgres，这是postgresql的管理员账户
su – postgres
# 通过该命令进入sql控制台，类似于oracle的sqlplus
psql
```
然后你就会进入sql控制台，接下来你将输入sql命令完成一些基本配置
```sql
-- 第一件事情是为改用户设置密码，以后很多配置文件里面有用到
\password postgres
-- 然后输入你自己喜欢的密码即可，本文将统一采用‘1q2w3e’作为我们的密码
-- 如果你想更换密码，可以通过命令
-- alter user postgres with password '1q2w3e'，很方便。
```
为自己的数据库的管理员账户配置好密码之后，现在你需要创建一个库的实例，就和oracle中的数据库实例类似，以提供给我们的paddles使用。本文将保持和ceph官方的统一，使用‘paddles’作为我们要创建的数据库名字。
``` sql
create database paddles;
-- 通过'\l'命令，我们可以查看到我们刚刚创建好的数据库
\l
-- 然后我们退出sql控制台，或者你可以直接按ctrl+d
\q
```
然后我们回到root的操作模式下
``` shell
# 为paddles的安装创建一个用户，并设置密码
# 本文中我们将创建名为‘paddles’的用户用于运行paddles
useradd -m paddles -g root -G root
# 为改账号设置密码
echo paddles:1q2w3e | chpasswd
# 创建完成之后，我们切换到paddles用户下操作
su - paddles
```
我们在创建paddles账号时并没有指定它的bash，如果你直接登录到paddles用户会有一些问题，所以我们都是直接先连接到root，然后再切换到paddles上即可。
``` shell
# 从github上克隆我们需要的代码
git clone https://github.com/ceph/paddles.git
# 或者你可以使用我们的 git clone https://github.com/H3C/paddles.git
# 下载好之后，进入到下载的文件夹中，执行
# 该命令为创建Python引以为傲的沙盒环境
# 沙盒大概是指该沙盒中的环境是独立，与系统环境互不干扰
virtualenv ./virtualenv
# 配置我们的config.py文件，从模板中复制一份然后修改，这种方式会很常见
cp config.py.in config.py
vi config.py

# 我们主要改两行，一个是server配置项，改成我们自己要监听的地址
# 一般就是本机的ip，监听端口我选择了8080，你可以随意，只要各处统一就好
server = {
    'port': '8080',
    'host': '172.16.38.101'
}

# 还有一处要修改的就是数据库的地址，在最下方
# 我们使用的是postgresql数据库，这里我们将之前配置的数据库信息填上
# 注释掉默认的url行，增加我们自己的
# 这个位置其实就是Python语法中的map，别忘记在逗号
'url' : 'postgresql://postgres:1q2w3e@localhost/paddles',


# 进入沙盒环境
source ./virtualenv/bin/activate
# 然后你就会发现自己的命令行前面表面你已经进入到沙盒环境中了
# 安装沙盒需要的相关依赖
pip install -r requirements.txt
# 初始化环境
python setup.py develop
# 创建表，也即在postgresql创建和初始化paddles需要的表结构
# 这里我一度官方的修改会导致这一步出问题
# 所以如果你在这里也遇到了问题，你可以使用前面说的H3C的源代码
pecan populate config.py
# 配置数据迁移工具
cp alembic.ini.in alembic.ini
vi alembic.ini
# 这里主要配置数据库信息
sqlalchemy.url = postgresql://postgres:1q2w3e@localhost/paddles
# 触发迁移工具生效
alembic stamp head
```
到此为止，你已经完成了paddles需要的所有配置。当然，你现在还是处于沙盒环境之后，沙盒环境无非就是使用沙盒内的Python编译器执行你的命令而已，你甚至可以在./virtualenv/bin/中找到这些命令，有兴趣可以自行查看。
现在你需要启动你的paddles了，有两种情况。

 1. 为测试
    仅仅是为了看一下，我的paddles配置正确了吗，能够正常运行了吗，那么你可以通过在沙盒中运行
```shell
pecan serve config.py
```
直接临时启动你的paddles，然后就可以通过你在config.py中配置的地址来查看你的成果了，按照我的配置的话，打开浏览器，输入地址：
http://172.16.38.101:8080/
然后，你就会看到一串JSON格式的数据返回给你了。
应该是类似于：
``` json
{"_help_": {"docs": "https://github.com/ceph/paddles", "extensions": {"Chrome": "https://chrome.google.com/webstore/detail/jsonview/chklaanhfefbnpoihckbnefhakgolnmc", "Firefox": "https://addons.mozilla.org/en-US/firefox/addon/jsonview/"}}, "last_job": "19 hours, 40 minutes, 22 seconds ago", "last_run": "21 hours, 1 minute, 28 seconds ago"}
```
这说明你的paddles已经可用了，它已经可以作为pulpito的存储后台来使用。
 2. 正式使用
    在install(1)中，我们已经说到要使用supervisord作为我们进程管理工具，这里我们将演示如何使用supervisord来管理我们的paddles。
（1）配置gunicorn
首先，我们要放弃使用pecan来运行我们的Python web服务，使用一个稍加封装的，更好的‘pecan’---- gunicorn，不必担心，你用不着重新安装它的环境，也一点都用不着去学，你只需要了解了解以下几个命令即可。
退到paddles用户环境，不退也可，都无所谓，只是编辑个文件而已
``` shell
vi gunicorn_config.py
```
将该文件改为以下内容，甚至可能它原本就已经是以下内容了，那就不用改了。

``` python
import os
import multiprocessing
_home = os.environ['HOME']

workers = multiprocessing.cpu_count() * 2
workers = 10
max_requests = 10000
#loglevel = 'debug'
accesslog = os.path.join(_home, "paddles.access.log")
#errorlog = os.path.join(_home, "paddles.error.log")

```
然后你就可以退出该用户了，关于如何使用supervisord管理它，我们将在后面的章节中弹到，就在本章节下第2个章节，很快。

## pulpito的安装部署
特殊说明（1）：
https://github.com/caibo2014/gooreplacer4chrome
改Web应用设计到谷歌的API，最好使用谷歌浏览器进行访问，当然，如果你是位经验丰富的程序员，相信你也有别的方法来代替Google-front-api等。
后面会相信阐述该问题的解决方法。

特殊说明（2）：
我们建议将paddles和pulpito安装一台机器，使用不同的端口而已，因为这两个都是非常小而且不需要耗费太多资源的，也省去了安装很多依赖的问题

随着安装步骤的逐渐进行，前面已经提到的比较详细的简单步骤和操作技巧将一一被简化，相信你在阅读本文时也会渐渐适应这样的一种风格，简化后省去了你不必要的阅读量。

（1）安装依赖
和上面paddles需要的依赖是一样的，我们已经安装过了，这里不需要任何操作了。

（2）创建用户，并切换到对应的用户环境
``` shell
useradd -m pulpito -g root -G root
echo pulpito:1q2w3e | chpasswd
su - pulpito
```
（3）克隆相应源码
```shell
git clone https://github.com/ceph/pulpito.git
```

（4）创建沙盒
```shell
virtualenv ./virtualenv
```
（5）编辑文件
```shell
cp config.py.in prod.py
vi prod.py
# 修改监听的地址和paddles的地址

server = {
    'port': '8081',
    'host': '172.16.38.101'
}

paddles_address = 'http://172.16.38.101:8080'

# 同时，我们需要关闭掉pulpito的debug模式
'debug': False,
```
（6）启动沙盒并安装依赖
```shell
source ./virtualenv/bin/activate
pip install -r requirements.txt
```
（7）启动pulpito
这个和上面的paddles一样，也分为两种情况。

 1. 为测试
```shell
   # 直接在沙盒内
   python run.py
```
然后打开浏览器，输入刚刚配置的监听地址：http://172.16.38.101:8081/
这个时候你应该能看到和http://pulpito.ceph.com/ 类似的界面，这说明你的pulpito也安装成功了。
 2. 正式使用
    正式使用把pulpito的运行线程交托给supervisord管理，下一章节讲解。

（8）关于打开界面非常慢，甚至卡住的情况
也就是前面特殊说明（1）提到的问题，这是由于该项目访问了谷歌的API的缘故，有经验的朋友直接查看本小节头给出的连接即可明白并解决问题了。
如果你没有处理过类似的情况，可直接将以下内容保存为:force_install_for_windows.reg
```dos
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist]
"1"="paopmncpffekhhffcndhnmjincfplbma;https://github.com/jiacai2050/gooreplacer4chrome/raw/master/updates.xml"

[HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Chromium\ExtensionInstallForcelist]
"1"="paopmncpffekhhffcndhnmjincfplbma;https://github.com/jiacai2050/gooreplacer4chrome/raw/master/updates.xml"

```
然后直接执行即可，本脚本也是来自于特殊说明（1）中的网址。

## supervisor的安装配置

（1）安装supervisor

这个和paddles还有pulpito都在一台机器上，其实我们前面安装依赖的时候，已经安装了supervisor了，如果你没有安装，再安装一次也可以。
```shell
# apt方式
apt-get install supervisor
# Python模块安装方式
pip install supervisor
```

（2）配置主文件
```shell
vi /etc/supervisor/supervisord.conf

# 该文件一般不需要配置，这里只是告诉你一下有这个文件，有什么疑问都可以去查看该文件

# 该文件规定了许多全局的配置，比如supervisord守护进程如何与supervisorctl控制台进行通信，如何将进程管理的UI通过HTTP发布等等。

# 如果你有一些特殊的需求，可以自行搜索百度supervisor，教程很多
```

（3）配置任务文件
正如主文件的默认的最后一行所说，它包含了一些其它的配置文件，我们称之为任务文件，它是用来描述一个任务的，也即supervisor应该监控哪些进程，执行哪些操作，都是在这些任务文件里面规定的。
这些文件都应该被放在supervisor默认规定的/etc/supervisor/conf.d目录下，想更改路径的话，可以在主配置文件中修改。
我们的两个任务文件分别被命名为：paddles.conf 和 pulpito.conf

paddles任务文件：
```shell
cat /etc/supervisor/conf.d/paddles.conf
```
```xml
[program:paddles]
user=paddles
environment=HOME="/home/paddles",USER="paddles"
directory=/home/paddles/paddles
command=/home/paddles/paddles/virtualenv/bin/gunicorn_pecan -c gunicorn_config.py config.py
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile = /home/paddles/paddles.out.log
stderr_logfile = /home/paddles/paddles.err.log

```

pulpito任务文件：
```shell
cat /etc/supervisor/conf.d/pulpito.conf
```
```xml
[program:pulpito]
user=pulpito
directory=/home/pulpito/pulpito
command=/home/pulpito/pulpito/virtualenv/bin/python run.py
environment=HOME="/home/pulpito",USER="pulpito"
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile = /home/pulpito/pulpito.out.log
stderr_logfile = /home/pulpito/pulpito.err.log

```

两个配置文件都比较简单，其中的command选项即我们跑这个守护线程时，守护线程需要干的事情，我们看到，其实我们配置的这两个守护线程无非也就是用我们刚才创建的沙盒环境来执行特定的命令而已，只不过我们刚才是手工做，现在交给supervisor来做。

（3）使用supervisor启动任务
```shell
# 通过supervisorctl控制台启动
supervisorctl start all
# 你也可以通过supervisord本身启动
# supervisord -c /etc/supervisor/supervisord.conf

# 启动之后你可以查看下这两个进程的状态
supervisorctl status

# 应该看到以下结果
root@client1:/etc/supervisor/conf.d# supervisorctl status
paddles                 RUNNING    pid 4872, uptime 2 days, 22:10:20
pulpito                 RUNNING    pid 4873, uptime 2 days, 22:10:20

```
到这里你已经成功使用supervisor来管理你的paddles和pulpito，你不用再担心因为重启而引发paddles或者pulpito不可用，supervisor会随时监测这两个线程的状态，一旦重现问题，它就会尝试重启它们。


## gitbuilder的搭建和使用
官方教程：https://github.com/ceph/gitbuilder

gitbuilder也可以说就是个apt-get的源，请参看：
http://gitbuilder.ceph.com/
这是ceph官方搭建好的gitbuilder。
gitbuilder相对来说没什么好搭建的，只是讲讲怎么使用它。
首先找一台性能比较好的机器，单独的用来做gitbuilder，物理机或者虚拟机都可以，但是性能请尽量好一点，不然你每编译一次，可能就要你一下午的时间。

（1）克隆项目源码
```shell
git clone https://github.com/ceph/gitbuilder.git
# 同样的，你需要做许多的更改以适应编译你自己的ceph
# 你可以克隆我们更改过的，这样你只需要稍作修改即可
# git clone https://github.com/H3C/gitbuilder.git
# 当然，我们还是会全面的讲一下修改的地方
```

（2）获取我们需要编译的代码
其实这个gitbuilder可以用于编译任何项目的，是个通用的框架。我们这里用它来编译ceph，所以我们需要获取我们的ceph代码
```shell
# 进入到目录中，gitbuilder只负责编译目录为build下的那些代码
# 所以我们把我们的ceph代码克隆到build文件夹下
cd gitbuilder
git clone https://github.com/H3C/ceph.git build
```
（3）修改分支脚本，只编译我们想要编译的分支
gitbuilder中有一个脚本文件是用来控制你需要编译的分支的，名为：branches.sh
我们可以对它稍加修改，只关注我们自己的分支，我这里使用的是比较粗暴的方法
```shell
# 在执行任何git指令之前，强行输出我想编译的那几个分支，然后直接退出
# 比如我只想编译分支“master”
echo "master"
exit 0
.
.
.
# 其实branches.sh里本身就提供了分支控制的语句
 if [ -x ../branches-local ]; then
     exec ../branches-local "$@"
 fi
# 这里它执行的这句话就是如果存在这个脚本就直接执行了，你也可以将你想要编译的分支写到这个脚本里。
方法很多，这些更改其实都是在autobuilder.sh中有调用到。
```

（4）修改build.sh
```shell
cp build.sh.example build.sh
vi build.sh
# 其实里面默认的那些语句对编译ceph都没什么用，可直接删除或注释
# 将build.sh的内容改为:
cp ../make-debs.sh .
chmod 777 make-debs.sh
./make-debs.sh /ceph_tmp/release
```

（5）创建make-debs.sh
上面我们拷贝了一份make-debs.sh到我们的ceph目录下并进行执行，那么这个make-debs.sh从哪里来呢，该文件存于ceph项目的根目录中。

```shell
# 我们可以直接用ceph自身提供的make-debs.sh来进行编译
# 该脚本位于ceph项目的根目录
# 你可以到ceph中去拷贝一份，然后稍作修改即可
```
这里我使用github的展现方式来表明要修改的地方，主要修改也就是增加了编译时的线程，去除打包到debian中的代码，以及添加一个version文件。
```github
diff --git a/make-debs.sh b/make-debs.sh
index b8d3e46..529af65 100755
--- a/make-debs.sh
+++ b/make-debs.sh
@@ -58,8 +58,8 @@ tar -C $releasedir -zxf $releasedir/ceph_$vers.orig.tar.gz
 #
 cp -a debian $releasedir/ceph-$vers/debian
 cd $releasedir
-perl -ni -e 'print if(!(/^Package: .*-dbg$/../^$/))' ceph-$vers/debian/control
-perl -pi -e 's/--dbg-package.*//' ceph-$vers/debian/rules
+#perl -ni -e 'print if(!(/^Package: .*-dbg$/../^$/))' ceph-$vers/debian/control
+#perl -pi -e 's/--dbg-package.*//' ceph-$vers/debian/rules
 #
 # always set the debian version to 1 which is ok because the debian
 # directory is included in the sources and the upstream version will
@@ -80,11 +80,7 @@ fi
 # b) do not sign the packages
 # c) use half of the available processors
 #
-: ${NPROC:=$(($(nproc) / 2))}
-if test $NPROC -gt 1 ; then
-    j=-j${NPROC}
-fi
-PATH=/usr/lib/ccache:$PATH dpkg-buildpackage $j -uc -us
+PATH=/usr/lib/ccache:$PATH dpkg-buildpackage -j120 -uc -us
 cd ../..
 mkdir -p $codename/conf
 cat > $codename/conf/distributions <<EOF
@@ -94,6 +90,7 @@ Components: main
 Architectures: i386 amd64 source
 EOF
 ln -s $codename/conf conf
+echo $dvers > version
 reprepro --basedir $(pwd) include $codename WORKDIR/*.changes
 #
 # teuthology needs the version in the version file
```

（6）修改autobuilder.sh
这个脚本文件才是整个builder真正的入口，前面的一切准备工作，最后都是被脚本所调用，稍有shell基础的朋友看下这个脚本就能明白整个项目的运作方式了。

我们这里对这个脚本稍作修改，以便它能够正确的将我们的编译好的deb包，放到正确的目录，方便我们后续通过web服务器将它发布出去。
同样使用github的风格展示
```github
+++ autobuilder.sh      2015-07-02 10:59:09.588364316 +0800
@@ -54,6 +54,12 @@
                trap "echo 'Killing (SIGINT)';  kill -TERM -$XPID; exit 1" SIGINT
                trap "echo 'Killing (SIGTERM)'; kill -TERM -$XPID; exit 1" SIGTERM
                wait; wait
+               mkdir -p /ceph_repos/ceph-deb-trusty-x86_64-basic/ref/${branch#*/}
+               cp -r --preserve=links /ceph_tmp/release/Ubuntu/{conf,db,dists,pool,trusty,version} /ceph_repos/ceph-deb-trusty-x86_64-basic/ref/${branch#*/}
+               echo $ref > /ceph_repos/ceph-deb-trusty-x86_64-basic/ref/${branch#*/}/sha1
+
+               mkdir -p /ceph_repos/ceph-deb-trusty-x86_64-basic/sha1/
+               ln -s /ceph_repos/ceph-deb-trusty-x86_64-basic/ref/${branch#*/} /ceph_repos/ceph-deb-trusty-x86_64-basic/sha1/$ref
+               rm -rf /ceph_tmp/release/*
        done
```

（7）运行
所有准备都完成了之后，我们要开始编译我们的项目了，直接运行
```shell
./start
```
其实该脚本就是运行了autobuilder.sh和一个文件锁操作

（8）如何了解直接的编译结果
所有的编译结果都会输出到当前目录的out文件夹下，这里面输出的其实是cgi文件，可以理解为较为高级、通用的网页文件，既然是网页文件，这个时候你就需要一个服务器来展示这些网页文件了。
建议你使用apache2。这个服务器安装极其方便，安装后通过简单的配置即可使其支持cgi文件。

1）安装apache2服务器
```shell
apt-get install apache2
```
2） 创建一个配置文件以支持cgi程序
```shell
vi /etc/apache2/mods-enabled/cgi.load

LoadModule cgi_module /usr/lib/apache2/modules/mod_cgi.so
AddHandler cgi-script .cgi .pl .py .sh

<Directory /var/www/html/gitbuilder>
Options +Indexes +FollowSymLinks +MultiViews +ExecCGI
AllowOverride None
Order allow,deny
allow from all
</Directory>
```
3）链接文件到/var/www/html下
apache2服务器默认的服务地址是/var/www/html文件夹下，为了更好使其能够展示我们的编译结果，我们做一个软连接到该目录下
```shell
ln -s "out文件夹对应的地址"/out /var/www/html/gitbuilder
```
4）解决权限问题
将out文件所在的目录以及父目录都赋权，比如我的存在家目录下~/repo
```shell
chmod 777 ~/repo -R
# 如果你不想以后都有这个麻烦，直接将家目录更改下权限
# chmod 777 ~ -R
# 都是内网环境，也不存在明显的安全问题
```
5）启动服务器并验证
```shell
service apache2 restart
```
打开浏览器，输入相应的地址：
http://gitbuilder-host-IP/gitbuilder
即可看到本次编译完成的情况
其实感觉根本没必要这么看，因为在编译的时候，是会输出到屏幕的，大概就能知道哪些成功或者失败了，或者从最后打包的情况，也能看出来。

6）做成apt-get源
  这一步才是我们真正的目的，编译完成了之后，结果是一大堆的deb包和很多的包信息文件，我们现在要做的就是将其发布到网上。
我们这里选择的服务器是nginx，这是为了方便我们以后做反向代理，多台机器进行编译时，发布地址可能不在一台服务器上，所以我个人感觉nginx是最好的选择，当然，这只是建议，具体什么服务器，由你自己选择，本文对如何使用nginx来完成这一任务，做一定的描述。

根据前面我们的配置，所有的deb包最后都拷贝到了/ceph_repos下
所以我们要做的事情很简单，就是将/ceph_repos这个目录发布出去，发布的时候带有目录结构方便在网络上查看。

以下前两个步骤，如果你直接使用apt-get install nginx的话就不需要了，可直接跳过查看如何配置nginx

 1） 下载nginx源码
```shell
# 下载的话直接搜索下nginx download就有了
# 解压nginx包，本文使用的是1.80
tar xzvf nginx-1.8.0.tar.gz
# 安装nginx依赖
apt-get install libpcre3 libpcre3-dev zlibc openssl libssl-dev libssl0.9.8
```
2）编译并安装nginx
```shell
./configure
make && make install
```
然后你需要配置一下环境变量
```shell
vi ~/.bashrc

# 添加一行
export PATH=$PATH:/usr/local/nginx/sbin

# 然后使更改立刻生效
source ~/.bashrc
```
 - 配置nginx.conf
这是nginx的配置文件，如果是apt-get的方式安装的话，好像在/etc/nginx下，如果是源码安装的话则在/usr/local/nginx/conf下
```shell
vi /usr/local/nginx/conf/nginx.conf
```
主要改两个地方：
 - 配置nginx使其默认的文件类型为text/plain
   这样就不会碰到没有类型的文件就直接下载了
```shell
default_type  text/plain;
```
 - 配置nginx服务器的根路径
   使用户直接访问本机IP时，可以跳转到/ceph_repos下。
```shell
    location / {
        # 打开目录控制，使我们的页面能以目录方式呈现给用户
        autoindex on;
        root   /ceph_repos;
    }

```
3）启动nginx并验证
```shell
# 启动nginx
nginx
# 停止nginx
nginx -s stop
# apt-get的方式
service nginx start|restart|stop
```
然后打开对应的网址如：http://172.16.38.102
你就可以看到类似于：http://gitbuilder.ceph.com/的效果了。

## NTP服务器安装配置
这个非常的简单，按照本文的风格，类似的小组件，我们只是简单的介绍一两个，由于这些小组件都十分的通用，大家在看到的时候可直接通过网络搜索教程即可。
```shell
apt-get install ntp

vi /etc/ntp.conf

# 规定哪些IP能访问本服务器
restrict 172.16.100.0 mask 255.255.0.0 nomodify
server 127.127.1.0
fudge 127.127.1.0 stratum 10
```
顺利完成0，重启下NTP就好，十分的方便
```shell
service ntp restart
```

## teuthology任务执行节点的安装
在本文中，一直称之为slave节点，这比较类似于Hadoop中的分级，master节点负责管理信息，然后布置任务给slave节点，slave节点负责完成这些任务，然后把结果信息反馈给master节点。

teuthology的slave节点，也称之为任务资源，其实就是一台台的装有Ubuntu系统的虚拟机，当然也可以是物理机，但是我们不建议那么做。

1）安装一台虚拟机
   我们安装的是Ubuntu14.0LTS，也建议你使用该系统
2）配置可远程ssh登录
   相信你前面的机器也是通过类似CRT，Xshell的工具登录并操作的，那么应该也已经知道如何配置了，这里再重提一下。
```shell
vi /etc/ssh/sshd_config
# 更改为下面行
PermitRootLogin yes
service ssh restart
```
3）安装ansible
```shell
apt-get install ansible
```
4）安装配置NTP
```shell
apt-get install ntp
# 并修改配置文件使其执行前面配置的NTP server
vi /etc/ntp.conf
# 注释掉那些原有的server，添加我们自己的
server "前面配置的NTP Server地址"
```
5）添加名为'ubuntu'的用户
此处只能添加名字为ubuntu的用户，添加其它名字都是不行，这也是teuthology这个平台不够完善的表现。
```shell
useradd ubuntu –m –G root –g root -s /bin/bash
echo ubuntu:1q2w3e | chpasswd
```
6）配置免密使用sudo命令
```shell
vi /etc/sudoers
# 添加行
ubuntu   ALL=(ALL)         NOPASSWD: ALL

```
7）情况apt-get源
```shell
mv /etc/apt/sources.list  /etc/apt/sources.list.bak
touch /etc/apt/sources.list
```
8）安装ceph相关依赖
该问题较为复杂，你可以通过尝试使用之前我们搭建的gitbuilder作为apt-get源，然后试着安装一下ceph，系统就会告诉你缺少哪些依赖，然后你需要去把这些依赖都下载下来并安装上，如果你连接着网络，这些依赖都可以通过apt-get的方式来安装，还是比较方便的

9）hostname和hosts匹配
由于ansible是一个去中心化工具，所以所有slave节点都可能要互相交互，所以但是teuthology传递给他们的是一个hostname而不是具体的IP，所以hosts文件就起到了转换这些hostname的作用，两个点注意。

 - 自己的hostname，请与127.0.1.1相对应
 - 其它人的hostname,所有节点请保持统一

10）防止pgp认证错误
apt-get pgp error，如果完全不了解的话可以先搜索下前面的关键字。

将你搭建的gitbuilder作为源，然后apt-get update，如果出现了apt-get pgp error错误的话则需要你手工处理一下。

处理方式也很简单，报错时它会提示给你一串数字，将这串数字注册一下就好。
```shell
apt-key adv --recv-keys --keyserver keyserver.ubuntu.com 6EAEAE2203C3951A
```

到此一个teuthology的slave节点就安装完毕了，然后你就可以通过虚拟机的各种克隆技术疯狂的克隆了，克隆30台左右就好，当然如果你是物理机的话那就没办法了，这也是我们不建议你使用物理机的原因之一。


## teuthology管理节点的部署

我们先讲teuthology主体的安装，而不先说git server等组件的安装时因为在安装完前面的组件之后，已经能够支撑teuthology运行一定的任务，所以我先讲如何安装teuthology，让大家快速的部署好环境并尝试着运行一些任务。

我们建议安装teuthology的机器应该是磁盘容量较大的，至少请在500G以上，当然20G的也可以运行，但是teuthology跑一次任务产生的日志文件大小可能就有20G，磁盘空间满了之后，你的任务将无法继续进行。

前面我们已经说过，随着安装的进行，我们对于一些小细节的描述将省去，比如这里安装各类依赖，势必要先配置好apt-get的源，经过前面的磨练，这样的步骤你已经非常熟练，这里就不再重复写出来浪费文章篇幅了。

### 系统环境配置
1）安装系统依赖
```shell
apt-get -y install git python-dev python-pip python-virtualenv libevent-dev python-libvirt beanstalkd
```
其中beanstalkd为teuthology所使用的任务队列组件，大家可以自行搜索下。

2）为调度者和执行者创建账号
不清楚调度者和执行者区别请参见install（1）
``` shell
useradd -m teuthology -g root -G root
echo teuthology:1q2w3e | chpasswd

useradd -m teuthworker -g root -G root
echo teuthworker:1q2w3e | chpasswd

```

3）分别给两个账号授予passwordless sudo access权限
``` shell
vi /etc/sudoers

# 添加下面两行

teuthology   ALL=(ALL)         NOPASSWD: ALL
teuthworker  ALL=(ALL)         NOPASSWD: ALL

```

4）创建配置文件
``` shell
vi /etc/teuthology.yaml

# 内容如下（部分请自行修改）：

# paddles所在服务器
lock_server: 'http://172.16.38.101:8080'
# paddles所在服务器
results_server: 'http://172.16.38.101:8080'
# 域名，创建slave节点时有用到
lab_domain: 'h3c-ceph.com'
# beanstalkd队列服务器，第一步安装的，就在我们本地，默认端口是11300
queue_host: 127.0.0.1
queue_port: 11300
# 本地归档，直接放在执行者的家目录下
archive_base: /home/teuthworker/archive
verify_host_keys: false
# 官方的是：http://github.com/ceph/，就是我们下载各种需要的组件源码的路径
# 这里暂时使用github上的，之后我们将搭建一个完整的git服务器替代它
ceph_git_base_url: http://github.com/H3C/
# 就是前面搭的gitbuilder的地址
gitbuilder_host: '172.16.38.102'
reserve_machines: 1
# 归档目录，直接写本机的地址加/teuthology即可
archive_server: http://172.16.38.103/teuthology/
max_job_time: 86400

```

5）安装其它依赖
这些依赖并不是在系统级别上使用，而是各个用户在执行命令时需要使用到
```shell
apt-get -y install git python-dev python-pip python-virtualenv libevent-dev python-libvirt beanstalkd
```
开发相关依赖
```shell
apt-get -y install  libssl-dev libmysqlclient-dev libffi-dev libyaml-dev
```

### 安装调度者

我们已经为调度者创建了一个用户teuthology，接下来的操作都在teuthology中进行。
```shell
su - teuthology
```

1）克隆代码并初始化环境
```shell
mkdir ~/src

# 你也克隆我们的,做了一些修改，比如可以关闭每次都去网上拉取这样的特性
# 更多的信息你可以通过查看我们的github地址来寻找
# git clone https://github.com/H3C/teuthology.git src/teuthology_master
git clone https://github.com/ceph/teuthology.git src/teuthology_master

# 进入到克隆好目录下并执行脚本 bootstrap
./bootstrap

# 该脚本为初始化各类环境的脚本，它会从网上去下载很多组件和脚本
# 一般来说，这个脚本是不会出错的
```

2）创建slave节点
这里的意思其实就是将一些我们已经安装好的slave节点的信息采集起来，然后传输给paddles，这样我们就知道一共有多少台可以利用的资源了，跑任务的时候就可以去用这些资源。

收集这些节点信息并最终存到数据库，对我们来说只要做一件事就好，那就是编辑create_nodes.py这个脚本，改动非常的小。

首先要做的就是获取这个脚本：
```shell
wget https://raw.githubusercontent.com/ceph/teuthology/master/docs/_static/create_nodes.py
```
因为这完全就是一个网络脚本，为了防止它不断的变化而导致本文的可用性，这里提供一下当时我们使用的脚本，如果没有更新话，你应该下载到和我一样的一个脚本。
我们将需要更改的地方也在文中标明了，只需要更改前面几行即可。

```python
#!/usr/bin/env python
# A sample script that can be used while setting up a new teuthology lab
# This script will connect to the machines in your lab, and populate a
# paddles instance with their information.
#
# You WILL need to modify it.

import traceback
import logging
import sys
from teuthology.orchestra.remote import Remote
from teuthology.lock import update_inventory

# 这里改为你的paddles地址，这是本文一直使用的paddles地址
paddles_address = 'http://172.16.38.101:8080'

# 你想创建的机器类型，也就是为你的slave节点分个类
# 什么类型名字其实无所谓，但等会你执行任务时默认为plana
# 指定为plana类型，运行任务时可以省去指定机器类型语句
# 建议你以plana, buripa, miraas作为类型名，方便和官方统一
machine_type = 'plana'
# 前面我们配置/etc/teuthology.yaml文件时已经指定了域名，相同就行
lab_domain = 'h3c-ceph.com'
# Don't change the user. It won't work at this time.
user = 'ubuntu'
# We are populating 'typica003' -> 'typica192'
# 这里更改一下编号，从哪一号到哪一号
# 这是需要修改的最后一行，后面都不需要修改了
machine_index_range = range(17, 22)

log = logging.getLogger(sys.argv[0])
logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(
    logging.WARNING)


def get_shortname(machine_type, index):
    """
    Given a number, return a hostname. Example:
        get_shortname('magna', 3) = 'magna003'

    Modify to suit your needs.
    """
    return machine_type + str(index).rjust(3, '0')


def get_info(user, fqdn):
    remote = Remote('@'.join((user, fqdn)))
    return remote.inventory_info


def main():
    shortnames = [get_shortname(machine_type, i) for i in machine_index_range]
    fqdns = ['.'.join((name, lab_domain)) for name in shortnames]
    for fqdn in fqdns:
        log.info("Creating %s", fqdn)
        base_info = dict(
            name=fqdn,
            locked=True,
            locked_by='admin@setup',
            machine_type=machine_type,
            description="Initial node creation",
        )
        try:
            info = get_info(user, fqdn)
            #log.error("no error happened")
            base_info.update(info)
            base_info['up'] = True
        except Exception as exc:
            log.error("{fqdn} is down".format(fqdn=fqdn))
            #log.error("some error: {0}".format(exc.strerror))
            log.error("the traceback is")
            s=traceback.format_exc()
            log.error(s)
            log.error("the error is ")
            log.error(exc)
            base_info['up'] = False
            base_info['description'] = repr(exc)
        update_inventory(base_info)
if __name__ == '__main__':
    main()

```

修改完成之后，把这个文件放到我们克隆的~/src/teuthology_master中，或者你刚才wget时直接放到该路径下也可以，之后执行以下该脚本即可。
```shell
python create_nodes.py
```
你一定很好奇，这些名字既然是随便取的，那么如何定位这些机器的IP呢，这其实是需要你在/etc/hosts文件中指定的，这也是teuthology平台的特性，都只是给出hostname，具体IP都是由hosts文件给出。

前面配置之后，产生的hostname的组成结构是：
```shell
machine_type + 3位数字 + '.' + lab_domain
```
比如我的机器类型为'plana'，正好是集群中的第3台机器，我的域名规定为h3c-ceph.com，那么最终产生的hostname是：
```shell
plana003.h3c-ceph.com
```
这时我就需要在/etc/hosts文件中为其指定对应的IP
```shell
plana003.h3c-ceph.com  172.16.38.143
```

3）验证是否已成功上传了slave节点信息
检验方式很简单，登录我们之前搭建的pulpito界面，点击右上方的node，选择ALL，即可查看我们当前拥有的所有的资源节点，如果有的话则代表你已经成功推送slave节点信息到数据库中了。

简单的看下各个节点的信息，你会发现所有节点都是处于锁住状态的，你可以通过类似于：
```shell
teuthology-lock --owner caibo --unlock plana003
```
的命令来进行解锁，在install（3）中，我们将学习更多的命令来帮助管理者这些资源节点，调度任务，管理执行者，查看任务队列等。

当然，执行该命令的前提是teuthology的执行目录已经被你加载到环境变量中了
```shell
echo 'PATH="$HOME/src/teuthology_master/virtualenv/bin:$PATH"' >> ~/.profile
# 即刻生效
source ~/.profile
```

### 安装执行者
执行者的安装相对简单

切换到teuthworker用户下

1）克隆源码并初始化环境
```shell
mkdir ~/src
git clone https://github.com/H3C/teuthology.git src/teuthology_master
cd ~/src/teuthology_master
./bootstrap
```

2）初始化执行环境
```shell
mkdir ~/bin
# 从网上下载该脚本
wget -O ~/bin/worker_start https://raw.githubusercontent.com/ceph/teuthology/master/docs/_static/worker_start.sh
```
出于同样的目的，我们还是向大家展示下我们获取到的脚本，以免脚本更新引起的误会

```shell

#!/bin/bash

# A simple script used by Red Hat to start teuthology-worker processes.

ARCHIVE=$HOME/archive
WORKER_LOGS=$ARCHIVE/worker_logs

function start_workers_for_tube {
    echo "Starting $2 workers for $1"
    for i in `seq 1 $2`
    do
        teuthology-worker -v --archive-dir $ARCHIVE --tube $1 --log-dir $WORKER_LOGS &
    done
}

function start_all {
    start_workers_for_tube plana 50
    start_workers_for_tube mira 50
    start_workers_for_tube vps 80
    start_workers_for_tube burnupi 10
    start_workers_for_tube tala 5
    start_workers_for_tube saya 10
    start_workers_for_tube multi 100
}

function main {
    echo "$@"
    if [[ -z "$@" ]]
    then
        start_all
    elif [ ! -z "$2" ] && [ "$2" -gt "0" ]
    then
        start_workers_for_tube $1 $2
    else
        echo "usage: $0 [tube_name number_of_workers]" >&2
        exit 1
    fi
}

main $@

```
这个脚本比较简单，就是调用了teuthology-worker而已。

3）配置环境变量
```shell
echo 'PATH="$HOME/src/teuthology_master/virtualenv/bin:$PATH"' >> ~/.profile

source ~/.profile

# ！！！你需要创建一个目录，不然执行启动时会报错
mkdir -p ~/archive/worker_logs
# 如果你是挂载的话，你还需要将这个目录的权限赋一下
```
现在你可以使用teuthology的命令了
尝试启动一个执行plana类型任务的执行者
```shell
worker_start plana 1
```
你会看到屏幕上有一些输出，说明已经开始在后台运行了，如果不幸出现错误，你可以根据具体的错误的信息进行解决，无非就是网络问题，权限问题。

你可以通过
```shell
killall -u teuthworker
```
来终结teuthworker用户拥有的所有进程

接下来你可以直接看install（3）来进行一些最基本的命令尝试，感受一下teuthology的运行和命令方式。
其实真正的想搭建好teuthology平台还是在于尝试，尝试各种命令，解读安装过程中的报错，分析执行日志中的报错，这样才能更好的掌控它。

## git server的搭建和使用
到了这里，我认为已经属于对teuthology由来初步的了解了，现在你应该知道teuthology的任何和运行方式其实是定义在许许多多的yaml文件中的，这些yaml文件定义了如何去执行任务。
在teuthology的管理节点上，启动执行者之前会尝试从网络上拉取一些代码，执行过程中，管理节点也会尝试拉取一些代码，这个比较容易解决，或者给这一台机器连上网络，使其能够上网拉取代码，或者按照我们的方式，稍微对其代码做一定的修改，则可以避免这样的情况。具体的修改可以参看我们的项目，前面已经多次提到：https://github.com/H3C/teuthology

但是对于在任务执行过程中，teuthology slave节点也会上网拉取信息，这个我们却没有特别好的办法，首先，这个从何处拉取代码是有ceph-qa-suite决定的，所以想要在执行过程中纯粹使用内网，首先就需要修改ceph-qa-suite，如何修改可以参考：https://github.com/H3C/ceph-qa-suite
修改了ceph-qa-suite之后能够解决一部分的上网问题，拉取qa的动作就会从你指定的git地址拉取，但是比较可怕的是，这许多的测试例中，有很多脚本和源码需要从你在/etc/teuthology.yaml中指定的ceph_git_base_url。

安装相关软件
```shell
# 安装git
apt-get install git git-core

# 安装git-deamon
apt-get install git-daemon-run
```
```shell
# 编辑配置文件
vi /etc/service/git-daemon/run
```

``` shell
cat /etc/service/git-daemon/run

#!/bin/sh
exec 2>&1
echo 'git-daemon starting.'
exec chpst -ugitdaemon \
  "$(git --exec-path)"/git-daemon --verbose --export-all --reuseaddr \
    --enable=receive-pack  --base-path=/git/
```
裸克隆代码到指定的目录
``` shell
# git clone http://172.16.100.2/gerrit/ceph.git ceph.git
git clone https://github.com/H3C/ceph.git ceph.git

cd ceph.git
# 修改配置文件，开放各类权限
# 如果不是裸仓库的话，应该默认都开放的，就无需配置了
vi config
```
``` shell
cat config

[core]
        repositoryformatversion = 0
        filemode = true
        bare = true
[remote "origin"]
        url = https://github.com/H3C/ceph.git
        fetch = +refs/*:refs/*
        mirror = true

[daemon]
        uploadpack = true
        uploadarch = true
        receivepack = true
        allowunreachable = true
```



``` shell
# 启停命令
sv down git-daemon
sv up git-daemon
```


## smtp邮件服务器

这可以在teuthology的源码做一些简单的修改

```
smtpserver = config.smtpServer or 'localhost'
smtpuser = config.smtpUser
smtpasswd = config.smtpPasswd
smtp = smtplib.SMTP(smtpserver)
if smtpuser is not None and smtpasswd is not None:
    smtp.login(smtpuser, smtpasswd)
```

或者自己在teuthology的主机上搭一个本地的smtp服务器

## git web
git http-backend
或者
gitweb

##pip服务器
由于在某些测试例中，如s3需要使用pip install安装软件，如果此时想保持在内网环境，则需要搭建一个pip服务器

###安装pip2pi工具
```
pip install pip2pi
```
或:
```
git clone https://github.com/wolever/pip2pi
cd pip2pi
python setup.py install
```

### 创建存放软件包的仓库
```
mkdir /root/pypi
```
/root下创建requirement.txt，并且将所有你需要的包放到requirement.txt里面

### 下载软件包并建立索引
```
pip2tgz  /root/pypi  -r list/requirements.txt

# 建立索引
# 保证在simple下面能有所有自己需要的包
dir2pi   /root/pypi

```

### 测试
```
pip install –i 你的IP地址:端口/simple
```

## DNS服务器
由于teuthology和ceph-qa中都存在许多测试用例是需要去上网的，但是如果纯粹通过修改代码来实现重定向到自己的服务器的话，是比较繁琐的，而且也无法保证后续与社区同步
``` shell
vi /etc/bind/named.conf.default-zones

zone "radosgw.h3c.com" {
        type master;
        file "/etc/bind/db.200";
};

```
radosgw.h3c.com为自己定义的域名
db.200为自定义文件名

``` shell
vi db.200

$TTL 604800
@       IN      SOA     radosgw.h3c.com.        root.radosgw.h3c.com.(
                                1 ; Serial
                                604800 ; Refresh
                                86400 ; Retry
                                2419200 ; Expire
                                604800 ) ; Negative Cache TTL
;
@               IN      NS      localhost.
@               IN      A       172.16.51.6
*             IN      A       172.16.51.6

```

172.16.51.6为该主机的IP
``` shell
vi /etc/resolv.conf
# 将DNS服务器改为主机IP
nameserver 172.16.51.6
```

``` shell
# 重启DNS服务
service bind9 restart
# curl+自己域名验证能否被解析
curl radosgw.h3c.com
```

## git web
http://serverfault.com/questions/72732/how-to-set-up-gitweb
