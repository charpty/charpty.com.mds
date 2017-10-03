> 笔者博客地址：https://charpty.com

## 关于工厂方法模式的误会
不太在意设计模式的同事会对工厂模式有极深的误解，总会把“工厂模式”与“静态工厂方法”混为一谈，什么是静态工厂方法？看一个简单的例子：
``` java
public class SimpleClientFactory {

	public static Client createClient(){
		return new Client();
	}
}
```
通过一个静态方法来创建实例，这种方式在代码中比较常见，但这并不是我们今天要说的工厂模式，它只是一个“静态工厂方法”。
个人觉得很难给模式一个语句上的定义，因为这些模式本身只是一些帮助我们养成好的代码习惯的一些建议，它们甚至算不上是一种规范。对于工厂模式，我觉得某一段定义说的是比较准确的。

**父类定义了创建对象的接口，但是由子类来具体实现，工厂方法让类把实例化的动作推迟到了子类当中。**

也就是说，父类知道什么时候该去创建这个对象，也知道拿到这个对象之后应该对这个对象做什么事情，但是不知道如何去创建这个对象，对象的创建由子类来完成。
之所以有这种设计模式，也是多年业务逻辑的积累导致，大多数业务场景下，对某一类对象总是要执行相同的流程，但是并不在意这些对象之间的微小差异，这种业务场景就非常符合工厂模式的设计。公共的父类决定了怎么去处理这一类对象，而子类决定了如何创建这些有着微小差异的不同对象。

既然是工厂方法模式，那什么是“工厂方法”？举个基础的例子：
``` java
// 这是一个网页爬虫类，它利用HttpClient来获取数据并分析
public abstract class WebCrawler {

	// 爬取网页数据
	public WebResult getWebInfo(String url) {
		HttpClient c = getClient();
		HtmlResult res = c.getPage(url);
		return processHtml(res);
	}

	// HttpClient是接口或者抽象类，下文统称为接口
	private HttpClient getClient() {
	    // 如果缓存中不存在client则创建
		HttpClient c = getFromCache();
		if (c == null) {
			c = createClient();
		}
		// 创建之后对client进行初始化
		initClient(c);
	}
	
	 // 提供一个抽象让子类来实现创建client
	 // 这个抽象方法就是“工厂方法”
	 protected abstract HttpClient createClient();
}
```

``` java
// A和B类型两种client工厂都不需要关心创建client前的逻辑判断以及创建后的流程处理，他们只关心创建对象 

class ATypeCrawler extends WebCrawler {
	
	HttpClient createClient() {
		return new ATypeClient();
	}
}

class BTypeCrawler extends WebCrawler {
	HttpClient createClient() {
		return new BTypeClient();
	}
}

```
工厂方法模式能够封装具体类型的实例化，**```WebCrawler```提供了一个用于创建```HttpClient```的方法的接口，这个方法也称为“工厂方法”**，在```WebCrawler``` 中的任何方法在任何时候都可能会使用到这个“工厂方法”，但由子类具体实现这个“工厂方法”。


## Spring中的工厂模式
Spring源码中有非常多的地方用到了工厂模式，几乎是无处不见，但是笔者决定拿大家最为常用的Bean来说，用Spring很多程度上是依赖它的对象管理，也就是IoC容器对于Bean的管理，Spring的IoC容器如何创建和管理Bean其实是比较复杂的，它并不在我们此次的讨论范围中。我们关心的是Spring如何利用工厂模式来实现了更加优良J2EE松耦合设计。
接下来我们就一起查看一下Spring中非常重要的一个类```AbstractFactoryBean```是如何利用工厂模式的。
``` java
// AbstractFactoryBean.java
// 继承了FactoryBean，工厂Bean的主要作用是为了实现getObject()返回Bean实例
  public abstract class AbstractFactoryBean<T> implements FactoryBean<T>, BeanClassLoaderAware, BeanFactoryAware, InitializingBean, DisposableBean {

// 定义了获取对象的前置判断工作，创建对象的工作则交给了一个抽象方法
// 这里判断了Bean是不是单例并且是否已经被加载过了（未初始化但加载过了，这个问题涉及到Spring处理循环依赖，以后会讨论到）
  public final T getObject() throws Exception {
        return this.isSingleton()?(this.initialized?this.singletonInstance:this.getEarlySingletonInstance()):this.createInstance();
    }
// 由子类负责具体创建对象
protected abstract T createInstance() throws Exception;
}
```
之所以这么写是因为这种写法带来了两个好处:

**（1） 保证了创建Bean的方式的多样性**
Bean工厂有很多种，它们负责创建各种各样不同的Bean，比如Map类型的Bean，List类型的Bean，Web服务Bean，子类们不需要关心单例或非单例情况下是否需要额外操作，只需要关心如何创建Bean，并且创建出来的Bean是多种多样的。

**（2） 严格规定了Bean创建前后的其它动作**
虽然子类可以自由的去创建Bean，但是创建Bean之前的准备工作以及创建Bean之后对Bean的处理工作是AbstractFactoryBean设定好了的，子类不需要关心，也没权力关心，在这个例子中父类只负责一些前置判断工作。

工厂方法模式非常的有趣，它给了子类创建实例的自由，又严格的规定了实例创建前后的业务流程。
     
## 依赖倒置原则
 
 工厂方法模式非常好的诠释了面向对象六大设计原则之一的依赖倒置原则：要依赖抽象，不要依赖具体类。
 对依赖倒置的原则这个解释有点过于笼统，不太好理解，到底是哪些依赖被倒置了呢？
 回想最开始的基础例子，如果不使用工厂模式，我们的代码可能是这样的
```
public class WebCrawler {

	public WebResult getWebInfo(int clientType, String url) {
		HttpClient c = getClient(clientType);
		HtmlResult res = c.getPage(url);
		return processHtml(res);
	}

	private HttpClient getClient(int clientType) {
		HttpClient c = getFromCache();
		if (c == null) {
			c = createClient(clientType);
		}
		initClient(c);
	}
	
	 // 根据不同的类型参数来创建不同的HttpClient
	private HttpClient createClient(int clientType){
		if (clientType == 1) {
			return ATypeClient();
		} else if (clientType == 2) {
			return BTypeClient();
		} else if (clientType == 3) {
			return CTypeClient();
		} else 
			......
	}
}
```
上述代码最大的问题就是违背了开放-关闭原则，对扩展开放，对修改关闭。当有新的```HttpClient ```加入，则需要修改```WebCrawler ```类的代码，但是```WebCrawler ```并不关心具体的```HttpClient ``` 的具体类型，它只知道可以使用```HttpClient ```来获取网页信息，然后它自己就可以对这些网页信息就行分析。目前的代码写法导致```WebCrawler ```依赖于具体的```HttpClient ```实现类。

如果使用工厂模式，则可以避免这样的尴尬，工厂模式使得```WebCrawler ```不必关心```HttpClient ``` 的具体类型，因为这些具体的```HttpClient ``` 是由子类具体创建的，自己根本不知道到底有哪些```HttpClient ```类型，它只关心使用。同样的，各个子类也只管着创建```HttpClient ``` 的实例，至于这些实例被拿去做什么事情，什么时候做，它们并不知情。

按理说，高层组件应该依赖于低层组件，低层组件为高层组件提供一些最基础的服务，但是工厂模式倒置了这一依赖现象，让低层组件反而要依赖于统一的抽象接口。
**工厂模式让高层组件（WebCrawler）和低层组件（ATypeClient|BTypeClient|......）都依赖于共同的接口（HttpClient），这倒置了原本的依赖模型，解除了高层组件和低层组件之间的强依赖关系**


## 小结
工厂模式是非常常用且容易理解的设计模式，它也很好的诠释了六大原则之一的依赖倒置原则，能够帮助写出松耦合且方便扩展的代码。
要知道，在程序的世界，唯一不变的就是变化的需求，所以代码的可扩展性相当重要。