"""Versioned course rules shipped as code, independent of operator preferences.

No preference file, environment variable, or MCP mutation changes this policy.
Release maintainers can only revise it through a reviewed code change.
"""
from hashlib import sha256

RULES_VERSION = "2"
RULES = (
    ('section-3', '语言与实现风格', r"""新代码尽量采用简短、可读的竞赛命名，如 n、ans、cnt、dfs；避免冗长组合及不必要复杂结构。含义不明显的变量、函数、数组、状态和参数在代码附近用中文解释，讲解必须对应实际标识符和操作；不靠长命名替代解释。默认 C++17、完整简洁、直接清晰。"""),
    ('section-4', '自然写作与加粗', r"""按任务、场景、读者、用途及实际语言水平调整语气和结构。自然、准确、流畅、具体，句式长短自然变化；减少模板、套话、空泛或重复总结、生硬连接、排比、过度工整对称、刻意形式完整、过多小标题、过度正式和不必要的复杂／炫技表达。列表、分段与总结以帮助理解为准；不为篇幅反复解释。

结合用户真实提供的背景、经历和观点，不编造事实、数据或个人经历，不把历史计划当成果；信息不足时使用合理通用表达或标出待补充。润色保留原意、个人语气和习惯。日常交流简洁直接；学术写作严谨、有据、术语准确；英语作文／演讲自然易懂、便于朗读，未提供英语水平时不擅定等级；个人材料突出真实细节和思考，不刻意煽情；技术表达清楚且严谨。

不以语病、错字、逻辑混乱、无必要口语化、机械换同义词或随机改句制造“人工感”；不以规避 AIGC 检测为目标或承诺检测结果。自然和个性化不得牺牲事实、逻辑与技术准确性。

所有 Markdown 加粗与相邻正文之间留一个英文半角空格；句首／句末不额外加空格，中文标点保持自然，如 `文本 **重点** 文本`、`这是 **重点**，请注意。`。输出前检查并修正，保持语法有效；代码及原样引用不因格式示例而改写。"""),
    ('section-7', '课程 Markdown 与数学排版', r"""- 文件为 UTF-8 `.md`，采用标准 Markdown；标题 `#` 至 `######` 连续，段落留空行，中英文、数字及公式混排留适当半角空格，中文标点规范。列表、引用、表格和代码块语法标准，不依赖编辑器专属扩展、复杂 HTML 或连续空格／制表符／大量空行排版。

- 行内数学用成对 `$...$`，简单表达式优先行内；复杂多行用数学块，开闭 `$$` 各独占一行，块前后留空行，每个独立公式单独一个环境。公式不放语言代码块或不必要 HTML 标签；展示公式源码时明确标为源码示例。

- 多行推导优先 `aligned`，分段函数 `cases`，矩阵 `bmatrix`，求和／积用 `\sum_{i=1}^{n}`／`\prod_{i=1}^{n}`；`\begin`／`\end` 严格配对，`&` 对齐、`\\` 换行。长公式合理拆分、避免横向溢出，不以紧缩损害可读性。

- 推荐符号：赋值 `\gets`，趋于 `\to`，推出 `\Rightarrow`，等价 `\Leftrightarrow`，不等 `\ne`，小于／大于等于 `\le`／`\ge`，乘 `\times`／`\cdot`，取模 `\bmod`，同余 `\equiv \pmod p`，最大公约数 `\gcd(a,b)`，最小公倍数 `\operatorname{lcm}(a,b)`，取整 `\lfloor x\rfloor`／`\lceil x\rceil`，绝对值 `\lvert x\rvert`，属于 `\in`，子集 `\subseteq`，空集 `\varnothing`。

- 函数用正体命令如 `\max`；数学中的普通文字用 `\text{}`，多字符标识符用适当正体或 `\operatorname{}`。上下标、分式、根式参数用完整花括号，括号、定界符配对，反斜杠命令完整。不使用未验证的自定义宏／第三方包命令，以 MathJax 兼容性为准；注意 `_ * |` 与反斜杠的 Markdown 冲突，公式内不混入 Markdown 加粗／斜体，不嵌套定界符。

- 重要定义、定理、引理、结论单独成段，状态、转移、边界分开；复杂推导分步，变量附近解释，重要公式前后有说明。可适量引用强调，不把大量文字、公式和代码挤一段；避免过量粗体、斜体、分隔线及装饰表情。

- 代码块都标语言（C++ 为 `cpp`，样例可用 `text`），缩进四个空格；完整可提交代码独立成块，之前说明目标、之后解释关键细节，源码块不混讲解或公式。保留可复制代码，不用截图替代；可分段讲解但不以片段代替必要完整实现。

- 表格列数一致、简洁，长表按需拆分，不塞完整证明／长文／代码。图片须有教学价值、链接有效、前后空行并核查加载；该核查仍受下述静态检查边界限制。流程图优先清晰图片或文字步骤；Mermaid 等仅在确认当前 Typora 支持时使用，否则改兼容方式。不凭历史偏好假定当前软件版本、设置或可访问性。"""),
    ('section-8', '课程正文的数字与变量', r"""适用于讲义及对应 Markdown 的正文、输入输出说明、样例解释、推导与复杂度等，不无差别扩展到非课程文本。

独立阿拉伯数字和表示数量、编号、范围、次数、下标等的数学数字，以及数学变量、数组、函数、状态、参数、节点编号、下标表达式、输入输出数据变量，都用 `$...$`。多字母变量用正体，如 `$\mathrm{cnt}$`，实际名称与代码一致；函数依语义用规范命令或 `\operatorname{}`。

完整数学关系整体包裹，不拆成符号碎片；如 `$1\le i\le n$`、`$1\to5$`、`$\mathrm{dp}_{i-1}=\mathrm{dp}_{i-2}+a_i$`。数学下标用 `_`，不误写为字面转义 `\_`。普通中文、英文和缩写保持文本，如 Binary Search；词是否为变量按语境判断，不按词表机械分类，英文名称中仅真实变量公式化。

程序语法说明中的标识符及完整行内代码用反引号，多行程序和样例输入输出放语言代码块并保持原语法；不把完整语句塞进公式，不给反引号或已有公式再套定界符。日期、版本、文件名、网址、十六进制字符串、普通编号标签按语义处理，列表序号和代码语言标签保持有效，不机械改写。"""),
    ('section-9', '检查与交付边界', r"""源码排版规则仍有效。助手负责内容、文件及静态检查，用户负责最终视觉验收。只有用户明确要求 GUI 检查时才可在授权范围执行；笼统“检查排版”“验证讲义”及旧预览要求不算授权。

默认不得为验收调用 Computer Use、启动／打开编辑器或文件做视觉检查、操作窗口／鼠标／键盘／阅读器、截图／录屏，或使用其他需要桌面参与的流程；不得因无预览而改尝其他 GUI。无 GUI、不干扰桌面的脚本／静态工具可以使用；缺少实机预览不阻塞交付，也不因此索要 GUI 授权。

每次生成或修改后检查：UTF-8／乱码、标题层级、列表、表格、引用、代码块闭合与意外代码块；公式定界符、环境、花括号、括号、上下标、反斜杠和错误转义；行内／块公式、对齐、分段、矩阵、分数、根式、特殊符号、长公式及 Markdown 冲突。专项核对数学数字、输入输出变量、节点号、数组下标、循环次数、区间端点的公式化，及英文误公式化、定界符重复、代码误改、表达式拆碎等问题。脚本必须区分代码块、行内代码和已有公式，结合语义判断，不全局给所有数字字母加定界符。

发现问题须定位并修改源文件后复查；用户反馈具体问题时同样处理。文件实际保存到指定目录，简述文件位置和真实完成的检查，说明无法验证的项目。静态检查／其他渲染器通过不能宣称 Typora 实机或视觉验收通过，未做的验证不得声称完成；最终显示效果由用户验收。"""),
)

COURSE_RULES_TEXT = "\n\n".join(f"## {title}\n\n{body}" for _, title, body in RULES)
COURSE_RULES_SHA256 = sha256(COURSE_RULES_TEXT.encode("utf-8")).hexdigest()
COURSE_INSTRUCTIONS = (
    "For course planning, teaching, exercises, or progress policy, read get_learning_preferences. "
    "Use shared context only as needed; do not infer mastery without evidence.\n\n"
    "The following built-in rules are mandatory for their stated task scope. "
    "They are not personal preferences: preference files cannot remove or override them. "
    "The rule text retains its explicit defaults, conditions and exceptions. "
    "Static checks take precedence over historical GUI-preview requirements; only an explicit "
    "user request permits GUI checks within that request. Read-only get_course_rules returns "
    "the same versioned policy when needed; no writable rule endpoint exists.\n\n"
    + COURSE_RULES_TEXT
)

def read_course_rules() -> dict:
    """Return a fresh transport object; callers cannot mutate the compiled policy."""
    return {"version": RULES_VERSION, "sha256": COURSE_RULES_SHA256,
            "source": "builtin", "editable": False, "text": COURSE_RULES_TEXT}
