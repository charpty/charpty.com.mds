现在微服务非常火，很多项目在使用，相信不少同学在其中负责一个或两个微服务模块，当你或者你的团队开发完某一个```service```，你有信心直接交付使用吗？

我一贯的观念，微服务绝不仅仅是写代码。它需要配合一系列自动化测试、自动化运维、契约化开发、灵活版本管理等等一系列的配合手段。


回到刚才的问题，交付前必须经过严格的测试，复杂的微服务依赖关系让人抓狂，```服务A```通过了调用```服务B```、```服务C```、```服务D```3个服务来完成业务功能，现在要对```服务A```进行测试。此时面对这两种选择：  

#### 启动所有依赖的微服务的方式
把```服务A```依赖的3个微服务都启动起来，然后```服务A```能够正常的完成功能。  

这样做明显的问题是太耗费资源了，你的开发机启动4个服务或许还能支撑，万一依赖10个服务呢，且```服务B```又依赖了```服务E```这种递归依赖情况非常的常见。

#### 模拟3个服务的返回结果

