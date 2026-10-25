# 新范围输入草稿 v3：载体与绑定（待确认）

本版只修输入载体，不是正式需求目录或执行合同。v1/v2及批准前快照均保留原字节；原始需求、旧330合同、生产代码、测试和历史运行不变。本步授权来源为用户 Sentinel_9eeddc0a2410819190e6bb201ee12452（2026-10-24 15:12 UTC，“同意”）。

## 实际活动输入

inputs/ 下7份UTF-8 Markdown是唯一拟传给普通公开入口的需求文本：第一份 --requirements，其余六份重复 --companion。不选择本目录的JSON、README、旧BMAD文档或转部署台账。普通heading模式会从主文件及companions收集全部61个原SM锚点；各块完整包含所属条款的前提/时机/要求/可观察结果/禁止、范围角色和依赖文本。不存在仅放在未读取JSON里的125条明细，305条均在实际section正文。

V1读取每块source_text；V3 frozen source projection读取这些真实entries；V4读取完整新source-index。这里是源码支持的静态载体路径，不是已经跑过compiler或worker。input-source-index.json只是独立静态索引，不送CLI、不替代canonical source-index。完整CLI语法见future-public-entry.json，其中out-dir尚未选择，任何执行仍需用户下一步批准。

## 来源与原文

61个原SM标识全部保留，SM-K05仍只在部署台账。原23行逐字保留在对应块的引用中，并由original-row-quotes.json记录原行hash和真实旧source_ref；引用前缀不属于旧原文。它们只作来源，新的活动section包含完整作者明细和范围限定，所以新text hash诚实变化。原先4锚点/15义务的V1潜在重绑定条件在本版不再成立；不能以“保留引文”冒称保留旧活动identity。

source-role-bindings.json区分本版7份作者有效输入与原9份交付规范/溯源文件、旧plan/index。旧文件只支持明确保留部分的来源身份，不能整体复活已移出BMAD查询、安装、生成/refresh或内部reviewer。每一活动块均携带范围限定，避免全局限制只在README而丢失。新文件不冒用旧路径、hash、context或typed selection身份。

## 依赖表达

dependencies.json保留218条记录。185条非删除关系逐条进入对应consumer的source_text；33条删除建议中，仍有效consumer的移除界限写入同块，已转部署consumer的关系只留台账/映射。4项批准继续生效：3项明确依赖共享核心旧O-CA335D988AF5对应行为，1项移除新增BMAD注册前置且保留builder/policy/projection/core的真实来源及时效；原权限owner不变。其余214条沿用前版草稿建议状态，没有把本步载体授权升级为全图合同批准。

文本按旧ID、有效锚点和实际保留生产行为明确前置，不伪造新O-ID。原生V6最终只接受真实V1生成O-ID的depends_on；旁置映射不会自动写入正式图。未来若生成，必须按真实输出对账305条原语义、依赖和AC，不能把SM/旧O字符串直接填进新图或手写authority。仅静态无环不证明模型会正确构图。

## 复用与成本限制

完整载体改为普通heading模式，61个活动source_text均变化，旧源引用也变化；可保留的原文仍真实保全，但不能承诺原先15条V1复用。旧V3/V4/QuickDev运行均不得重标为当前证明。没有导入缓存或实际测命中。此方案优先保证完整真实消费，**若以后授权普通生成，按没有已证明V1/V3/V4命中的成本评估**；是否值得执行由用户决定。

## 检查及本步结束

静态校验见static-verification.json：7文件均低于256KiB；61锚点、305完整条款、330映射、25转部署；23原文逐字引用；185候选关系无悬空/重复/环；4批准决定覆盖，未生成合同或新正式ID。旧条款明细仅去掉原SM-SC标题作为分块方式，原内容完整进入对应section，适用限定保持。

未验证：未运行V0A/V1/V3/V4、模型、测试或消费链；正常入口的实时VDD查询、当前policy/发布状态、模型精确提取数量、实际depends_on/切片和缓存命中仍须未来授权后的真实门禁判断。普通输入无损承载已具备静态依据，但不能把本文件称为执行ready或已计划完成。未修改编译器，不恢复BMAD，也不push/PR/CI查询。完成后停止等用户决定下一步。
