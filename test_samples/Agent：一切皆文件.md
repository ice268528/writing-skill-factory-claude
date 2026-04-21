# Agent：一切皆文件
- 公众号：AGI Hunt
- 原文链接：https://mp.weixin.qq.com/s/ulmVG3_yrfy-7EofRgnyGw

一个叫 Mintlify 的文档平台最近干了一件很是巧妙的事：给自家 AI 文档助手，造了一套假的文件系统。


Mintlify 虚拟文件系统

然后，Agent 会以为自己在用 grep 搜文档、用 cat 读页面、用 ls 浏览目录。实际上，每一条命令都被拦截了，翻译成了数据库查询。

Agent 完全不知道自己用的是「假终端」。但效果，比用真的还好。

01

## RAG 撞墙

Mintlify 之前用的是标准 RAG 流程：把文档切块、向量化、存进 Chroma 数据库，用户提问时检索语义最相关的片段喂给模型。

大多数场景下还算管用。但碰到下面的两类问题，就不太灵了。

一种是答案散落在好几个页面里。用户问的是一个跨页面的配置流程，向量检索只返回语义最接近的几个片段，而正确答案需要把三个不同页面的内容串起来才行。

另一种是精确匹配。用户想找某个 API 的具体参数格式，向量检索返回的是语义相近但细节对不上的内容。

**向量检索的本质是「语义碰运气」，碰到需要精确定位的场景，就有点力不从心了。**


RAG 语义碰运气 vs Agent 精确定位

其实回过头看，这里有一个认知惯性：大家不知不觉把 RAG 等同于了向量搜索。

但需要注意的是，RAG 里的 R 是 Retrieval，检索，本就可以是任何方式。

全文搜索是 Retrieval，SQL 查询是 Retrieval，让 Agent 自己用 grep 翻文件，当然也算 Retrieval。

**把 RAG 绑死在向量数据库上，是早期技术路径的惯性。** 那时候模型还不太会用工具，多轮搜索和纠错能力也差，向量检索算是当时最省事的方案了。

Mintlify 的思路也就是从这里开始转弯的：与其继续优化向量检索的准确率，不如换一种检索方式。让 AI 像开发者翻代码一样翻文档，靠定位和搜索，靠管道组合，而不只是靠语义相似度。

02

## 造个假壳

那具体怎么让 AI「翻文档」呢？

他们最早试过一条直接的路：给每个用户起一个微型虚拟机，把文档仓库克隆进去，让 Agent 在真实文件系统里操作。

效果倒是不错。但代价嘛……

会话启动要等 46 秒（克隆仓库、启动 VM、挂载文件系统），按每月 85 万次对话算，一年光计算成本就超过 7 万美元。对于只读的静态文档来说，实在太重了。

然后他们换了个思路：

**Agent 不需要真的操作系统，只需要一个足够逼真的幻觉。**

有点像拍电影。Agent 面前的终端窗口，就是一个精心搭建的片场布景：目录结构、文件内容、命令反馈，看起来和真的一模一样。但推开那堵墙，后面连着的是 Chroma 数据库。


真沙箱 vs ChromaFS 对比

ChromaFS 就是这么来的。

它基于 Vercel Labs 的开源项目 just-bash（一个用 TypeScript 重写的 bash 子集）构建。just-bash 负责解析命令和管道逻辑，提供了一个可插拔的 `IFileSystem` 接口，ChromaFS 就是这个接口的实现：把所有文件操作翻译成 Chroma 数据库查询。


那接下来的问题就是：文档怎么变成「文件」？五条核心命令（`ls`、`cd`、`find`、`cat`、`grep`），又分别怎么伪装？

03

## 文档变文件

映射规则其实，很直觉。

Mintlify 的文档站本身就有层级结构：每个章节是一个分类，每个页面有一个 URL slug。

ChromaFS 直接把这套结构搬了过来：**章节变目录，页面变文件。**

比如一个文档站的 `getting-started/quickstart` 页面，在 ChromaFS 里就变成了 `/docs/getting-started/quickstart` 这个路径。Agent 用 `ls /docs/getting-started/` 就能看到这个目录下有哪些页面，用 `cat /docs/getting-started/quickstart` 就能读到完整内容。

整棵目录树以 gzipped JSON 的形式预存在 Chroma 的一个特殊文档 `__path_tree__` 里，附带每个路径的 `isPublic` 和 `groups` 元数据。

服务器启动时解压一次，加载到内存里：文件路径存成 `Set<string>`，目录到子项的映射存成 `Map<string, string[]>`。


文档站到文件系统的映射

也就是说，`ls`、`cd`、`find` 这三个目录操作，全部在内存里完成，**一次网络请求都不用发**。Agent 跑一条 `find /docs -name "auth*"` 遍历整棵树，走的是纯内存查表，毫秒级响应。

这三条命令，算是最好伪装的。因为它们只跟目录结构打交道，不碰文件内容。

04

## 拼回整页

`cat` 就没那么轻松了。

Agent 执行 `cat /docs/getting-started/quickstart` 时，ChromaFS 得从 Chroma 里取出这个页面的完整内容返回给它。

但 Chroma 里并没有存完整页面。

做 RAG 的时候，每个页面都被切成了若干个 embedding chunks，一个页面可能被拆成 5 个、10 个甚至更多的片段。

所以 ChromaFS 得反过来把它们拼回去：根据文件路径提取 slug，用 slug 去 Chroma 里查所有匹配的 chunks，按 `chunk_index` 排序，然后拼接成完整的页面内容返回。

拼好的页面会缓存起来，下次再 cat 同一个文件就不用重新查库了。


cat 的 chunk 拼接过程

还有个巧妙的细节。有些客户的文档里包含巨大的 OpenAPI 规范文件，动辄几千行，存在客户自己的 S3 桶里。

ChromaFS 用了一种「懒加载文件指针」的机制：目录树里有这个文件的路径，但只有 Agent 真的去 cat 它的时候才会去 S3 拉取内容。平时不占内存，也不占带宽。

那写操作呢，怎么办？

一律返回 `EROFS`（Read-Only File System）错误。Agent 能随便看，但改不了任何东西。整个系统无状态，不用担心清理和数据污染。

到这里，`ls`、`cd`、`find`、`cat` 都搞定了。

但还剩一个最难的。

05

## 伪装 grep

grep 为什么最难呢？

`ls` 和 `find` 只需要内存里的目录树，不碰文件内容，毫秒级就能返回。`cat` 只读一个文件，查一次 Chroma 拼一下就够了。

但 `grep -r "OAuth" /docs/` 是递归搜索。它要扫描这个目录下**所有文件**的内容。如果 `/docs/` 下有 500 个文件，按 cat 的逻辑那就是 500 次数据库查询，再加上 chunk 拼接。走网络 IO 的话，这个延迟 Agent 是等不起的。

偏偏 grep 又是 Agent 用得最频繁的命令……毕竟精确字符串搜索恰好是向量检索最不擅长的事，也是 Agent 最想依赖 grep 来做的。

ChromaFS 的做法是绕过逐文件扫描，把 grep 拆成三步。

**第一步，粗筛。**

拦截 grep 命令，解析出搜索模式和 flag。如果是固定字符串搜索（`grep -F`），就用 Chroma 的 `$contains` 元数据过滤；如果是正则表达式，就用 Chroma 的 `$regex` 查询。

这一步利用数据库自身的索引能力，把候选文件从上千个过滤到几十个。

**第二步，预取。**

把这几十个候选文件的内容，一次性批量从 Chroma 拉出来，塞进 Redis 缓存。一次批量查询，代替几十次甚至几百次的单独查询。

**第三步，精确匹配。**

让 just-bash 在内存中对缓存的内容跑完整的正则匹配。这一步的结果才是最终返回给 Agent 的。


grep 的三步伪装术

**数据库粗筛、缓存预取、内存精确匹配。三步下来，Agent 觉得自己只是跑了一条普通的 grep。**

再说权限控制。

ChromaFS 在初始化时根据用户的 session token 裁剪文件树：没权限的路径直接从内存的目录树里删掉，后续所有 Chroma 查询也会带上相同的过滤条件。Agent 连这些路径都看不到，自然也就不存在越权的问题了。

比起在 Linux 容器里折腾 chmod、用户组和独立镜像，这种方式简洁多了。

06

## Agent 的母语

ChromaFS 上线后，每天处理超过 3 万次对话，服务几十万用户。

但这个项目真正让我想展开一讲的原因，其实不在性能数据，在它背后的思路：**与其给 AI 造新工具，不如给它一个它已经「会用」的旧接口。**

Hacker News 上关于这篇博客的讨论里，有这么一条评论：

> “ 换成自定义工具，Agent 立刻掉 50 点智商。

为什么会这样呢？

在于 LLM 的训练数据。

Stack Overflow 上有几百万条 shell 相关的问答，GitHub 上有数不清的 bash 脚本，man page 覆盖了每一条命令的每一个参数。`grep -r "pattern" --include="*.md"` 这种用法，LLM 在训练阶段可能已经见过几十万次了。

而你定义的那个 `search_documents(query="xxx", filter={...})` API 呢？训练数据里一条都没有。

Agent 只能靠 schema 描述去「猜」怎么用，极易产生幻觉。

**而 LLM 对 POSIX 命令的理解深度，远超它对任何自定义工具 schema 的理解。**


Agent 的训练数据分布

还有一层，文件系统接口天然支持组合。

`grep "OAuth" docs/ | head -5`，Agent 信手拈来。`find docs/ -name "*.md" | xargs grep "redirect_uri"`，也毫无障碍。

这种管道组合能力，是 POSIX 工具链 50 年沉淀下来的设计精髓。

用你自定义 API 想实现同样的过滤和截取？那得专门设计接口参数，而且 Agent 还不一定能正确拼出来。

Unix 在 1970 年代提出了「Everything is a file」的哲学：把设备、进程、网络连接统统抽象成文件，让所有工具复用同一套接口。

现在这套哲学意外地在 AI 时代复活了。

没人刻意要复古，只是 LLM 的训练数据，天然偏向了 POSIX 工具。

**文件系统，恰好是 Agent 的「母语」。**


POSIX 管道组合 vs 自定义 API 调用

而我们常用的 Claude Code 的设计也印证了这一点，泄露的代码也进行了证实：[Claude Code 源码泄露，全面剖析【长文】](https://mp.weixin.qq.com/s?__biz=MzA4NzgzMjA4MQ==&mid=2453482208&idx=1&sn=e2ec922e157fed8ccfb731ed6b9d7b1f&scene=21#wechat_redirect)


它没有给 Agent 造一套精心设计的专属 API，直接给了真实的 shell 访问权限。Agent 用 grep 搜代码、用 cat 读文件、用管道组合操作，效果比任何定制工具都好。

火山引擎最近开源的 OpenViking 也走了类似的路，用 `viking://` 虚拟文件系统协议来组织 Agent 的上下文：记忆、资源、技能全部映射成文件路径和目录结构。

思路和 ChromaFS 不完全一样，但底层逻辑相通：**用 Agent 最熟悉的接口，去封装它需要操作的一切。**

07

## 边界

当然，这套方案也不是到处都能用的。

Hacker News 上有人提到：Mintlify 做的是结构化的技术文档，天然适合「页面 = 文件、章节 = 目录」的映射。但如果是公司内部那种东一块西一块、没什么层级的知识库呢？

文件系统隐喻能成立，前提是数据本身得有清晰的层级结构。没有层级，就没有目录树，`ls` 和 `find` 也就没了用武之地。

也有人指出，ChromaFS 本质上就是 GraphRAG，只不过图的形状是一棵文件系统树。粗筛用的还是 Chroma 的向量和元数据查询，只是在上面包了一层 POSIX 的壳。

**文件系统接口的甜蜜点，大概就在于：文档结构清晰、对精确匹配要求高、读多写少。**


文件系统接口的适用光谱

技术文档、API 文档、代码仓库，这些天然适合。内部 wiki、聊天记录、碎片化笔记……就未必了。

但换个角度来看，这其实也说明了一件事：现在模型的工具调用能力上来了，让 AI 自己决定怎么找信息，反而比预设一条固定的检索管道更灵活。

至于那个「工具」长什么样，是 POSIX 命令、是 SQL 查询、还是自定义 API，取决于你的数据结构和 Agent 的熟悉度。

Mintlify 选了文件系统，因为他们的文档天然有层级，而且 Agent 对 POSIX 命令足够熟悉。

而从 1970 年的 Unix，到 2026 年的 AI Agent，「一切皆文件」这句话的含义变了，但核心没变。

**用一套所有人都懂的接口，去抽象复杂性。**

**差异在于，现在的「所有人」里多了一位：Agent。**

◇ ◆ ◇

相关链接：

•  Mintlify 博客原文：https://www.mintlify.com/blog/how-we-built-a-virtual-filesystem-for-our-assistant 

•  just-bash（Vercel Labs）：https://github.com/nichochar/just-bash 

•  Hacker News 讨论：https://news.ycombinator.com/item?id=47618223 

•  OpenViking（火山引擎）：https://github.com/volcengine/OpenViking