> 笔者博客地址：https://charpty.com
> Spring源码解析系列均基于Spring Framework 4.2.7

### 把第三方系统的方法搬到本地
HttpInvoker是常用的Java同构系统之间方法调用实现方案，是众多Spring项目中的一个子项目。顾名思义，它通过HTTP通信即可实现两个Java系统之间的远程方法调用，使得系统之间的通信如同调用本地方法一般。

HttpInvoker和RMI同样使用JDK自带的序列化方式，但是HttpInvoker采用HTTP方式通信，这更容易配合防火墙、网闸的工作。
## 服务端实现
服务端主入口由```HttpInvokerServiceExporter```实现，它的工作大致流程如下
![服务端处理流程](/images/spring/httpinvoker/httpinvoker_server_bind_flow.png)

```HttpInvokerServiceExporter```实现了```HttpRequestHandler```，这使得其拥有处理HTTP请求的能力，按照Spring MVC的架构，它将被注册到```HandlerMapping```的```BeanNameMapping```中，这设计到Spring MVC如何处理请求，可以关注我的相关文章。
服务端的重要任务就是读取并解析```RemoteInvocation```，再返回```RemoteInvocationResult```，剩下的都只是标准IO流的读写。

## 客户端实现
客户端的实现也很好理解，主入口为```HttpInvokerProxyFactoryBean```, 和Spring用到的众多设计相同，该类的结构使用了模板设计方法，该类提供实现了几个模板方法，整体逻辑由父类```HttpInvokerClientInterceptor```的实现，主要流程如下
![客户端处理流程](/images/spring/httpinvoker/httpinvoker_client_invoke_flow.png)

我们最关心的是当我们调用接口的方法时，```HttpInvoker```是如何做到调用到远方系统的方法的，其实```HttpInvokerProxyFactoryBean```最后返回的是一个代理类（Cglib Proxy或者Jdk Proxy），我们调用接口的任何方法时，都会先执行```HttpInvokerClientInterceptor```的```invoke()```方法。

```
public Object invoke(MethodInvocation methodInvocation) throws Throwable {
// 如果是调用toString()方法则直接本地打印下方法信息
if (AopUtils.isToStringMethod(methodInvocation.getMethod())) {
return "HTTP invoker proxy for service URL [" + getServiceUrl() + "]";
}
// 构建RemoteInvocation对象，服务器和客户端统一使用该类进行通信
RemoteInvocation invocation = createRemoteInvocation(methodInvocation);
RemoteInvocationResult result;
try {
// 使用JDK自带的HttpURLConnection将序列化后的invocation的发送出去
  result = executeRequest(invocation, methodInvocation);
} catch (Throwable ex) {
  throw convertHttpInvokerAccessException(ex);
}
try {
  return recreateRemoteInvocationResult(result);
}
catch (Throwable ex) {
  if (result.hasInvocationTargetException()) {
   throw ex;
  }
 else {
  throw new RemoteInvocationFailureException("Invocation of method [" + methodInvocation.getMethod() +
"] failed in HTTP invoker remote service at [" + getServiceUrl() + "]", ex);
}
}
}

```
### 小结
HttpInvoker的实现就像学TCP编程时的“时间服务器”一样，是个经典且容易理解的HTTP通信编程范例，结合Java的序列化和简单的封装，让程序员可以像调用本地方法一样调用第三方服务器的方法，非常方便。