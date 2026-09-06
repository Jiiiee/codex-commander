# `check_package.py` 路径检测契约 v0.5 草案

状态：人工已于 2026-09-07 批准检测边界；本文件现冻结供 Codex 与 Claude 做最终定向复核。该批准尚不授权修改代码，只有两位复核者确认同一哈希可稳定测试后才进入实现。

核实基线：`52b10dc4ce43d2f68109094cf725eaefa4a8acf6`

## 1. 目标与边界

本检查器在发布前发现打包文本中误留的、指向某个开发设备或具体账户的绝对路径。它保护发布包的可移植性和整洁度。

本版只判断本文列出的路径、URL 书写形式和有限编码。没有列入的情况必须归为 `out_of_scope`，不得由实现者或评审者临时扩大。

## 2. 扫描文件集合

- 以 `RELEASE_CHECKSUMS.txt` 的文件条目作为唯一扫描集合，校验清单自身除外。
- 每个清单条目都必须完整读取；能以 UTF-8 解码的文件全部进行路径检查，不依赖扩展名。
- v0.2.0 发布包定义为纯文本包：清单中的每个条目都必须能以严格 UTF-8 解码；否则由包结构检查直接报错，不得跳过。`text_encoding` 的行号定义为：首个无效字节之前出现的 `0x0A` 字节数量加一。未来如需加入图片等二进制文件，必须先修改本契约并重新批准。
- 清单之外的文件不由路径检查器处理；是否属于多余文件由既有“文件集合一致性”检查负责。

## 3. 必须拒绝的路径

### 3.1 路径段定义

- 路径分隔符之间的非空连续内容构成一个路径段。普通文本中的路径 token 由 ASCII 空白或以下任一字面字符终止：`"`、`'`、反引号、`(`、`)`、`[`、`]`、`{`、`}`、`<`、`>`、`,`、`;`、`!`、`?`、`，`、`。`、`；`、`：`、`！`、`？`、`、`、`（`、`）`、`【`、`】`、`《`、`》`、`「`、`」`、`『`、`』`。句点 `.` 不单独终止路径，以免破坏文件名。
- 路径 token 必须从文件开头、ASCII 空白或上一条列出的普通文本终止符之后开始。出现在其他字符之后的 `/Users/...` 等子串不构成本版绝对路径；例如 `backup/Users/alice/config` 按第 6 节作为相对路径处理。
- “具体段”指不是第 6 节占位符的非空路径段。
- 下列 POSIX 前缀按字面大小写匹配；Windows 规则采用 ASCII 大小写不敏感匹配。该不对称是刻意规则，不根据运行机器改变。

### 3.2 macOS 与 Linux

以下根路径本身或其后代必须拒绝：

- `/Users/<具体账户>`
- `/Volumes/<具体卷名>`
- `/private/var/folders`
- `/var/folders`
- `/private/tmp`
- `/opt/homebrew`
- `/home/<具体账户>`
- `/root`

`/private/tmp` 与 `/tmp` 即使在 macOS 上可能指向同一位置，本检查器仍按文本拼写分类：前者拒绝，后者按第 6 节允许。

裸 `/Users`、`/Volumes`、`/home` 没有给出具体账户或卷名，明确归为 `out_of_scope`；`/root`、`/private/tmp`、`/opt/homebrew` 本身已经是完整路径，仍须拒绝。

### 3.3 Windows

以下形式必须拒绝，盘符和关键目录名采用 ASCII 大小写不敏感匹配，`/` 与 `\` 可以混用：

- `<盘符>:\Users\<具体账户>` 及后代
- `<盘符>:\ProgramData` 及后代
- 完整 UNC：`\\<主机>\<共享>\<至少一个后续路径段>`

UNC 只有在主机和共享两个段 **都** 是第 6 节角括号占位符时才允许；任一段为具体值即拒绝。其他 Windows 盘符绝对路径不属于本版。

只有主机与共享、没有后续路径段的 `\\fileserver\team` 不构成本版“完整 UNC”，明确归为 `out_of_scope`。

### 3.4 出现位置

上述路径出现在普通文本、URL userinfo、query、fragment、URL 前后文本，或第 5 节有限解码结果中，都必须拒绝。

## 4. HTTP(S) URL path 的唯一豁免

只有合法 HTTP/HTTPS URL 的 path component 可以包含形似本机路径的网络资源名。userinfo、query、fragment 及 URL 之外的内容不豁免。

文档结构边界只在原始 UTF-8 文本上识别，先固定 URL、普通文本和结束符的原始位置，再对各自内容执行第 5 节解码。解码得到的 `)`、`]`、`>`、空白或其他字符只能参与路径分类，不能反过来改变已经固定的文档结构边界。

本版只认可三种边界明确的形式：

1. **Markdown inline link/image，无 title**：`[文字](https://example.test/Users/alice/guide)`、`![说明](https://example.test/Users/alice/image.png)`。URL 必须紧跟 `](` 开始，并在原文中第一个字面 `)` 结束。本版不定义反斜杠转义，`\)` 中的 `)` 仍是结束符。结束符之前出现 ASCII 空白时，该形式不被识别。带可选 title 的写法不获得豁免，可改用 autolink。
2. **尖括号 autolink**：`<https://example.test/Users/alice/guide>`。内部不得出现未编码的 ASCII 空白、控制字符或 `>`。
3. **独立 bare URL**：从文件开头或 ASCII 空白之后开始，并且由 ASCII 空白或文件结尾结束。句号、逗号、引号、括号、强调符等紧贴 URL 时不获得豁免。

URL path 需要字面括号、title 或与排版符号相邻时，用户应改写为边界清楚的 inline link 或 autolink。

### 4.1 URL 合法性的最低规则

- scheme 为 `http` 或 `https`，大小写不敏感；
- authority 存在且 host 非空；authority 不含原始反斜杠、ASCII 空白或控制字符；
- 端口如存在，必须为十进制 `0–65535`；
- 支持普通域名、IDN、IPv4 和 bracketed IPv6；IPvFuture 不属于本版。Unicode host 在转换前不得包含 Unicode `Cc`、`Cf` 或 `Z*` 类字符，并且每个 label 必须能由 Python 3.10–3.13 标准库 `idna` codec 转换为 ASCII；否则不获得豁免；
- `%29`、`&rpar;` 等编码字符属于 URL 内容，不是文档层面的结束符；
- URL 不符合最低规则时，不获得 path 豁免。

## 5. 有限解码

### 5.1 两种转换

- **percent 转换**：只把完整 `%HH` 中代表 ASCII 字符的 triplet 转为该 ASCII 字符；其他 triplet 和残缺 `%` 保留原文。
- **entity 转换**：只处理带分号、解码结果为 ASCII 的 HTML5 named entity，以及带分号、结果为 ASCII 的十进制或十六进制 numeric entity；其他 entity 保留原文。

### 5.2 三层的正式含义

- 从原文状态开始，对整个候选窗口分别尝试两种转换；
- 最多三个 **总转换步骤**，不是每种转换各三次；
- 采用去重的广度遍历，深度 0–3 的唯一状态总数最多 15；
- 原文和每个唯一状态都按同一规则检查；
- 只有第四步以后才显现的内容属于 `out_of_scope`；非法或残缺编码本身不单独报错。

该定义是结果模型。实现可以采用流式或窗口方式优化，但对契约 fixture 必须产生相同结果。

## 6. 必须允许的占位符与通用路径

### 6.1 占位符

角括号占位符的完整文法为：`<[A-Za-z][A-Za-z0-9_-]*>`，并且必须占满整个路径段。

允许：

- `/Users/<user>/project`
- `/Users/<user>`
- `/Volumes/<volume>/project`
- `/Volumes/<volume>`
- `/home/<user>/project`
- `/home/<user>`
- `C:\Users\<user>\project`
- `\\<server>\<share>\path`
- `\\<server>\<share>`
- `$HOME/project`、`${HOME}/project`、`~/project`、`%USERPROFILE%\project`

占位符只替代它所在的机器识别段，后面可以没有额外叶子路径，POSIX、Windows 用户路径和 UNC 均适用。例如 `/Volumes/Data/<user>/x` 仍因具体卷名 `Data` 被拒绝；UNC 的主机和共享必须同时使用占位符。环境变量形式只在这里列出的根位置生效，不嵌入 UNC。

### 6.2 通用路径

以下文本必须允许：

- `/tmp/example`
- `/srv/app`
- `/mnt/data`
- `/media/example`
- `/data/example`
- `/opt/vendor/tool`
- 相对路径，如 `docs/guide.md`、`scripts/check_package.py`

`/opt/homebrew` 是第 3 节明确拒绝项；其他 `/opt/...` 不因 `/opt` 前缀单独拒绝。

## 7. token、窗口与工作量

- 本节所有长度都按 Python 解码后字符串中的 Unicode code point 数量计算；一个 code point 计为一个“字符”，不按 UTF-8 字节数计算。`N` 是原始文件严格 UTF-8 解码后的字符数。
- 单个候选 token 的原文跨度最长 8,192 字符；即使由文件结尾结束，超过 8,192 字符的已识别路径或 URL 候选仍拒绝为“候选过长”。
- 单个分析窗口固定为 16,384 字符，相邻窗口固定重叠 8,192 字符；文件必须从头到尾覆盖。
- 窗口起点固定为 `0, 8192, 16384, ...`，只要起点 `< N` 就生成窗口 `text[start:min(start+16384, N)]`；不得额外生成一个与既有内容重复的“贴尾窗口”。空文件生成零个窗口。
- 一个原文跨度不超过 8,192 字符的候选必须完整落入至少一个窗口。
- 每个唯一解码状态只允许一次从左到右的提取扫描；不得从每个 `&`、`%` 或结束符重新扫描同一长后缀。

测试计数器统一定义为：

`work = 所有转换接收的字符数 + 所有 tokenizer/classifier 接收的窗口字符数`

硬性门槛：

- 唯一状态数 `≤15`，转换深度 `≤3`；
- 单窗口 `≤16,384` 字符，候选 token 原文跨度 `≤8,192` 字符；
- 增长倍率只在 `N ≥ 131,072` 字符时验收：同一个确定性 fixture generator 使用相同单元和前缀分别生成 N 与 2N，要求 `work(2N) / work(N) ≤ 2.2`。小于该阈值的输入只检查绝对上限，不用增长倍率判定；
- `work(N) ≤ 64N + 524,288` 字符。该常数容纳最多 15 个唯一状态和 50% 窗口重叠，不通过缩小解码范围换取性能数字。

墙钟时间只记录观察值，不作为跨机器发布门禁。

## 8. 用户可理解的错误结果

拒绝时至少报告：文件、原文行号、类别和改写建议。类别使用固定值 `machine_path`、`url_boundary`、`candidate_too_long` 或 `text_encoding`。同一处同时满足多个类别时，固定优先级为 `text_encoding` > `candidate_too_long` > `url_boundary` > `machine_path`。

报告同时输出稳定的 `hint_kind`：`machine_path` 对应 `use_placeholder`，`url_boundary` 对应 `rewrite_url`，`candidate_too_long` 对应 `reduce_token`，`text_encoding` 对应 `fix_utf8`。测试断言 `hint_kind`，不锁定自然语言句子。面向用户的文字必须与该类型一致：URL 边界建议改写为 `[文字](URL)` 或 `<URL>`；具体设备路径建议使用第 6 节相应占位符；超长候选建议拆短；编码错误建议保存为 UTF-8。

路径类行号始终是原始 UTF-8 文件的 1-based 行号。原文直接命中时，报告匹配首字符所在行；路径只在解码结果中显现时，每个解码字符保留其原始 source span，报告解码后匹配首字符所对应原始 span 的起始行。解码产生的换行不得改变报告坐标。`text_encoding` 使用第 2 节定义的原始字节换行算法。

同一文件可合并重复类别，但不得只返回 `Machine-specific path: <文件名>`。

## 9. 明确不支持

- HTTP(S) 以外 scheme 的 URL path 豁免；
- 完整 CommonMark、HTML DOM 或浏览器级 URL 提取；
- Markdown inline link 的可选 title；
- 没有分号或残缺的 entity、解码为非 ASCII 的 entity；
- 超过三个总转换步骤、Base64、压缩或加密文本；
- IPvFuture bracketed host；
- macOS/Linux 前缀的非标准大小写变体；
- 裸 `/Users`、`/Volumes`、`/home`；
- `Users`、`ProgramData` 之外的普通 Windows 盘符绝对路径；
- 只有具体主机与具体共享、没有后续路径段的 UNC，如 `\\fileserver\team`；使用双占位符的同形写法由第 6 节明确允许；
- 判断 `/srv`、`/mnt`、`/media`、`/data`、普通 `/opt` 是否实际属于某台设备；
- 发布清单之外的文件和其他模块，如 `project_records.py`、行为 Runner 或侧边栏协作。

独立评审发现本节情况时，只记录为限制或后续改进，不作为当前缺陷或扣分项。

## 10. 验收标准

1. 建立独立 JSON fixture，字段至少为 `id`、`input`、`expected`、`clause`、`form`；`expected` 只能是 `reject`、`allow`、`out_of_scope`。`reject` fixture 可增加 `expected_report`，字段为 `file`、`line`、`category`、`hint_kind`，用于验证第 8 节；不验证报告内容的 fixture 可以省略该对象。fixture 不锁定自然语言句子，也不引用实现内部正则、常量或私有函数。
2. 必须覆盖第 2–8 节的原文、Windows 大小写、UNC、percent、带分号 entity、两种转换交替、userinfo/query/fragment、三种 URL、占位符、8,192/16,384 字符边界、原文行号和错误信息。
3. 同一 fixture 在 Python 3.10–3.13、macOS 与 Linux 上分类一致；Windows 路径文本分类也必须由平台无关 fixture 覆盖。
4. 第 7 节计数门槛全部通过；墙钟只记录。
5. 完整单元测试、独立契约 fixture、包检查、校验清单和一次真实 hosted CI 全部通过后，才能把实现标为符合。
6. 只有违反第 2–8 节或本节硬性验收项才能阻断本版；第 9 节只能登记。

## 11. 变更控制

- 人工批准后，本文件以哈希冻结。
- 实现 Agent 不得自行缩小或扩大范围；发现成本或误报问题必须回到 COD-37。
- Codex 与 Claude 使用同一哈希独立设计 fixture。范围外输入不扣分。
- 若复核要求修改契约，必须生成新版本并重新进行双方复核；不得静默改动已冻结文件。
