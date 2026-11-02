# -*- coding: utf-8 -*-
"""
Batch 1 revision of 11-1_修改稿.docx.

Principles:
- Read the existing copy; never touch 11-1.docx.
- Replace only pure-text paragraphs (no OMML equations, no drawings).
- Preserve the first run's character formatting when replacing text.
- Replace selected tables in place; keep all other tables/figures/equations.
- Save to a temporary file, then atomically replace the working copy.
"""
import os
import shutil
from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

SRC = r"C:\Users\Administrator\Desktop\xlwcc\11-1_修改稿.docx"
TMP = r"C:\Users\Administrator\Desktop\xlwcc\11-1_修改稿_tmp.docx"
FIG10 = r"C:\Users\Administrator\Desktop\xlwcc\_review_work\fig10_scenario_logic.png"

doc = Document(SRC)

# ---------------------------------------------------------------- helpers
def set_text(p, text):
    """Replace paragraph text while keeping the first run's formatting."""
    if p.runs:
        p.runs[0].text = text
        for r in p.runs[1:]:
            r._element.getparent().remove(r._element)
    else:
        p.add_run(text)


def set_run_font(run, name="宋体", size=10.5, bold=None):
    run.font.name = name
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), "宋体")
    rFonts.set(qn("w:ascii"), "Times New Roman")
    rFonts.set(qn("w:hAnsi"), "Times New Roman")


def shade_cell(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tcPr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell(cell, text, bold=False, size=9, align=WD_ALIGN_PARAGRAPH.CENTER,
             font_color=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.first_line_indent = None
    run = p.add_run()
    for i, part in enumerate(str(text).split("\n")):
        if i:
            run.add_break()
        run.add_text(part)
    run.bold = bold
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    if font_color is not None:
        run.font.color.rgb = font_color
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), "宋体")
    rFonts.set(qn("w:ascii"), "Times New Roman")
    rFonts.set(qn("w:hAnsi"), "Times New Roman")
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def build_table(rows, widths_cm, font_size=9, header_size=9,
                aligns=None, shade="D9E2F3"):
    n_rows = len(rows)
    n_cols = len(rows[0])
    t = doc.add_table(rows=n_rows, cols=n_cols)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    if aligns is None:
        aligns = [WD_ALIGN_PARAGRAPH.CENTER] * n_cols
    for j, w in enumerate(widths_cm):
        t.columns[j].width = Cm(w)
        for cell in t.columns[j].cells:
            cell.width = Cm(w)
    for i, row in enumerate(rows):
        tr = t.rows[i]
        trPr = tr._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        if i == 0:
            trPr.append(OxmlElement("w:tblHeader"))
        for j, val in enumerate(row):
            cell = t.rows[i].cells[j]
            is_header = (i == 0)
            set_cell(cell, val,
                     bold=is_header,
                     size=header_size if is_header else font_size,
                     align=aligns[j])
            if is_header and shade:
                shade_cell(cell, shade)
    return t


def replace_table(old_table, rows, widths_cm, font_size=9, header_size=9,
                  aligns=None, shade="D9E2F3"):
    new_table = build_table(rows, widths_cm, font_size=font_size,
                            header_size=header_size, aligns=aligns, shade=shade)
    old_table._tbl.addnext(new_table._tbl)
    old_table._tbl.getparent().remove(old_table._tbl)
    return new_table


def add_caption_before_table(table, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = None
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text)
    set_run_font(r, "宋体", 10.5, bold=False)
    table._tbl.addprevious(p._p)
    return p


# ---------------------------------------------------------------- capture refs
p = doc.paragraphs
p3 = doc.paragraphs[3]         # Heading "1 引言" (captured before insertions)
p195 = doc.paragraphs[195]     # Heading "4.3 ..." (captured before insertions)
p232 = doc.paragraphs[232]     # Heading "参考文献" (captured before insertions)
t_candidates = doc.tables[1]   # Table 2
t_demand = doc.tables[2]       # Table 3
t_dc = doc.tables[5]           # Table 6
t_policy = doc.tables[6]       # Table 7
t_cost = doc.tables[8]         # Table 9
t_fleet = doc.tables[9]        # Table 10
t_conn = doc.tables[10]        # Table 11
p_t10_cap = next(pp for pp in doc.paragraphs if pp.text.strip().startswith("表10 不同车队结构"))
p_t10_note = next(pp for pp in doc.paragraphs if pp.text.strip().startswith("注：三组车队数量均为算例假设"))
p_fig12_cap = next(pp for pp in doc.paragraphs if pp.text.strip().startswith("图12 候选配送中心启用成本"))

# ---------------------------------------------------------------- paragraph replacements
TEXTS = {}

TEXTS[0] = "货运限行政策下城市商超配送路径优化与配送中心启用阈值研究——以武汉市某连锁商超为例"

TEXTS[1] = (
    "摘要：针对货运限行条件下城市商超配送的道路可达性、混合车队配置与配送中心布局问题，"
    "以武汉市某连锁商超568家门店、2个现有配送中心和4个理论候选中心为算例，将区域、车型、"
    "时段及桥隧差异化限行规则转化为情景化有向可达性矩阵，构建考虑有限混合车队与候选中心启用决策的"
    "选址—路径模型，并设计“固定基准配对+重新优化”的三情景比较框架。结果表明：同一固定基准方案在"
    "日间限行矩阵下成本增加337.01元/日（3.37%）；日间限行下重新优化使成本较限行基准降低约691.2元/日"
    "（6.69%），但其中遗传算法仅贡献88.03元/日（0.85%），有向2-opt贡献603.18元/日（相当于限行基准"
    "成本的5.84%），路径层局部搜索是成本改善的主要来源；优化方案较无限行基准低354.20元/日（3.54%）。"
    "候选中心日启用成本为1,000元时未启用新增中心；固定排列条件下的持平阈值约为277.57元/中心·日，"
    "200元/日独立重算的持平阈值约为272.74元/中心·日，且该解使用7辆燃油车、25辆新能源车，较8F+25N"
    "主算例少280元/日固定成本。研究还表明，现行矩阵仅近似编码二环线及可识别桥隧，第三条三个严管片区"
    "和第四条其余八个分片区尚未逐路段编码；燃油货车可达性以及中型纯电动货车在严管片区的可达性均可能"
    "被高估。本文结论适用于上述算例与矩阵假设，不构成对企业实际运营或政策效果的因果推断。"
)

TEXTS[2] = (
    "关键词：货运限行；选址—路径问题；混合车队；纯电动货车；有向可达性矩阵；遗传算法；"
    "配送中心启用阈值"
)

TEXTS[9] = (
    "与已有研究相比，本文的边际贡献体现在三个方面。第一，在建模层面，将城市货运通行管理中同时存在的"
    "区域、车型、时段以及桥梁、隧道等特殊路段差异化规则，统一转化为车型—情景对应的有向道路可达性"
    "矩阵并作为硬约束进入选址—路径模型，较之仅以低排放区、碳排放或进入惩罚等单一政策情景刻画的做法"
    "（如万玉春[12]、Wang等[11]），提供了更细的政策—路网映射；但本文矩阵仍为部分编码，其覆盖边界在"
    "4.5节说明。第二，在评价设计层面，通过让S1与S2共享同一套固定基准路径、仅切换道路矩阵的配对设计，"
    "把限行对既定配送组织的直接影响从网络重新优化的改善效果中分离出来，并通过GA与2-opt的分解避免将"
    "重新优化效果整体归因于联合决策。第三，在应用层面，基于武汉市门店坐标与OSM路网给出568门店规模算例，"
    "并对车队结构、候选中心启用成本开展敏感性分析，为限行条件下既有配送中心是否需增设节点提供条件阈值"
    "型判据，而非全局最优或真实场地可行性结论。"
)

TEXTS[10] = (
    "围绕上述研究目标，本文重点考察三个问题：第一，在现有配送中心、门店分配、车型配置及门店访问顺序"
    "保持不变时，日间货运限行对既定配送方案的道路距离和配送成本产生何种影响；第二，在相同限行条件下，"
    "允许模型自主决定候选配送中心启用、门店分配、车型选择及车辆访问顺序，能否降低配送系统总成本，成本"
    "改善在遗传算法与路径层2-opt之间如何分配；第三，车队结构及候选配送中心启用成本变化将如何影响优化"
    "结果，候选中心启用的条件阈值是多少。鉴于企业未提供历史车辆清单和配送线路，本文将固定基准方案作为"
    "统一的算例比较基准，不将其表述为企业实际运营方案；同时，区域限行及特殊路段禁行规则通过情景化道路"
    "矩阵近似表达，且矩阵仅部分编码政策条款，相关结果仅用于分析本文算例条件下的优化表现。本文所称"
    "“选址可行性”仅指成本层面的可行性，不涉及用地、交通、政策合规等真实场地可行性；“联合优化”指模型"
    "同时决定候选中心启用、门店分配、车型选择及路径，不表示该解为全局最优。"
)

TEXTS[139] = (
    "在K=4条件下，568家门店被划分为4个空间簇，并形成4个理论候选配送中心。基于坐标审计后的门店位置，"
    "候选中心位置和簇内门店数量按K-means重新计算；各候选中心空间位置及门店聚类结果如图9所示，具体结果"
    "见表2。"
)

TEXTS[155] = (
    "为构造配送中心与门店之间的距离和行驶时间矩阵，本文使用OpenStreetMap/Geofabrik湖北省道路Shapefile，"
    "筛选研究区域内的可能机动车道路，并按道路单行属性构建有向路网。568家门店、2个现有配送中心及4个"
    "候选中心共形成574个模型节点。道路几何在UTM 50N投影下计算长度，再通过节点接入连接将模型节点关联"
    "到道路图。"
)

TEXTS[165] = (
    "载重量按模型中的有效载重上限处理，不等同于车辆总质量。武公交规〔2023〕64号对中型新能源厢式载货"
    "汽车的豁免门槛为车长不超过6 m、总质量不超过8 t。本文将纯电动货车的有效载重上限设为4.5 t，作为"
    "满足该门槛车型的代表性假设，该值不指向某一具体公告车型；燃油货车的载重上限设为5.0 t。两类车的"
    "单次固定使用成本分别假设为280元和230元，均不含能源费用。需要特别说明：若按4.12 t的有效载重计算，"
    "8F+25N车队的总载重为143.0 t，低于本文模拟需求144.447 t，主算例在该参数下不可行，至少需增加1辆"
    "新能源车（8F+26N，总载重147.12 t）。因此，本文将4.5 t定义为代表性有效载重上限，相关结果应理解为"
    "该假设下的算例结果，而不是对某一具体车型运输能力的可行性结论。纯电动货车单条路径有效里程上限设为"
    "300 km，用于近似反映载重和路况对可用续航的影响，并非具体车型的官方标称续航。"
)

TEXTS[174] = (
    "此外，表7列示了第三条三个全日禁行严管片区，但第四条(二)—(九)八个7:00—22:00分片区未逐项列示；"
    "当前道路可达性矩阵仅近似编码二环线及以内区域和可识别桥隧，未逐路段编码第三条三个片区及第四条"
    "(二)—(九)。由于三个严管片区位于二环内，其日间禁行已被二环规则近似覆盖，未编码主要影响22:00—"
    "次日7:00；第四条(二)—(九)多位于二环外，未编码会高估这些片区的燃油日间可达性。此外，第五条城市"
    "货车通道、第六条金山大道、第七至十条中型及以上车辆限制及第十一条老旧柴油货车限制亦未编码。上述"
    "遗漏使燃油货车可达性既可能被高估，也可能因货车通道未编码而被低估，净方向不确定。还需注意，第三条"
    "三个片区对本文4.5 t中型纯电动货车同样全日禁行（仅微型、轻型厢式/封闭式车在部分时段例外），矩阵"
    "未编码该规则，故新能源车在三个片区的可达性也可能被高估。"
)

TEXTS[186] = "表7 货运限行政策条款及本文矩阵编码情况"

TEXTS[187] = (
    "注：本表汇总第一至十一条与本文车型相关的通行规则及矩阵编码情况；第四条(二)—(九)以汇总行表示，"
    "未逐项列示八个片区的边界；第五至十一条仅列示与本文5 t燃油货车和4.5 t中型纯电动货车相关的限制。"
    "当前道路可达性矩阵仅近似编码二环线及以内区域和可识别桥隧，未逐路段编码第三条三个片区及第四条"
    "(二)—(九)，故燃油货车在核心城区及二环外片区的可达性可能被高估；第三条三个片区对本文4.5 t中型"
    "纯电动货车同样全日禁行（仅微型、轻型厢式/封闭式车部分时段例外），矩阵未编码该规则，新能源车在"
    "三个片区的可达性也可能被高估；同时第五条货车通道未编码可能低估燃油可达性，净方向不确定。道路"
    "矩阵结果应理解为算例近似，不等同于官方逐路段法律可达性数据。"
)

TEXTS[194] = (
    "三种情景的比较逻辑如图10所示。S1与S2共享同一套固定基准配送组织，仅切换道路通行矩阵，用于识别"
    "限行对既定方案的直接影响；S3则在日间限行条件下重新决定候选中心启用、门店分配、车型选择及访问"
    "顺序，用于评价限行条件下的重新优化效果。需要说明：S1并非无限行条件下的最优配送方案，S2基准又是"
    "在日间限行矩阵下构造的，因此S2−S1是同一S2可行方案在两种矩阵下的配对差异，不是政策因果效应；"
    "S3−S2同时包含遗传算法与路径层2-opt的贡献，其分解见4.3节。"
)

TEXTS[198] = (
    "从局部搜索效果看，三组随机种子的遗传算法输出在有向2-opt前平均成本为10,245.02元/日，执行路径层"
    "有向2-opt后平均降至9,641.84元/日，平均减少603.18元/日，降幅为5.89%（相对遗传算法输出）。三组"
    "结果的降幅分别约为5.98%、5.86%和5.82%。将S3相对S2的约691.2元/日降幅分解为两段：S2→GA输出为"
    "88.03元/日（0.85%），GA输出→2-opt为603.18元/日（相当于S2成本的5.84%），2-opt占S3−S2的87.3%。"
    "因此，本文6.69%的成本改善主要来自路径层有向2-opt，而非遗传算法对候选中心启用、门店分配及路径"
    "构造的搜索；将S3−S2整体解释为“选址—路径联合优化”的贡献会高估联合决策的作用。有向2-opt仅调整"
    "单条路径内部顺序，不改变中心启用、门店分配和车型，故其贡献应理解为路径重排效应。该结果不构成全局"
    "最优性证明。"
)

TEXTS[202] = (
    "表9汇总了主算例三种情景的配送成本及路径结果。S1和S2采用同一套固定基准方案，S3为三组随机种子经"
    "遗传算法和路径层有向2-opt处理后的平均结果。三种情景均完成568家门店的唯一服务，主算例均使用8条"
    "燃油车路径和25条新能源车路径；在候选中心日启用成本为1,000元时，S3未启用新增配送中心。由于S3同时"
    "包含GA与2-opt，S3−S2不能整体归因于选址—路径联合优化，需结合4.3节的分解解读。"
)

TEXTS[203] = (
    "注：日总成本=候选中心启用成本+车辆固定使用成本+里程能源成本；现有配送中心固定成本未计入。S3为"
    "3组随机种子运行均值，日总成本样本标准差为12.83元/日；S1、S2为同一固定基准方案的配对评价结果。"
    "S2−S1=+337.01元/日（+3.37%），S3−S2=−691.2元/日（−6.69%），S3−S1=−354.20元/日（−3.54%）。"
    "S3−S2中，GA输出阶段贡献88.03元/日（0.85%），有向2-opt贡献603.18元/日（相当于S2的5.84%），"
    "2-opt占87.3%。车辆固定成本占S1、S2、S3日总成本的79.9%、77.3%和82.9%，成本结构以固定成本为主。"
    "行驶时间按总里程/25 km/h估算，不代表车辆并行运行下的总完工时长。"
)

TEXTS[204] = (
    "在主算例8F+25N车队配置下，S1的日总成本为9,996.04元，总配送里程为3,843.54 km；S2的日总成本为"
    "10,333.05元，总里程为4,176.27 km。由于两种情景采用完全相同的配送中心归属、门店分配、车型配置和"
    "访问顺序，S2相较S1增加337.01元/日，增幅为3.37%；总里程增加332.73 km，增幅为8.66%。由于固定成本"
    "不变，337.01元/日全部来自能源成本增加（2,006.04→2,343.05元/日，+16.80%）；其中燃油车里程由"
    "870.39 km增至1,112.42 km（+27.81%），新能源车里程由2,973.15 km增至3,063.85 km（+3.05%），燃油车"
    "里程增幅更高是能源成本增幅高于总里程增幅的原因。该差额反映本文构造的固定基准方案在日间限行道路"
    "矩阵下的成本变化，而非企业历史线路的实测政策影响；S2基准又是在日间限行矩阵下构造的，故该3.37%"
    "应理解为配对算例差异，不是政策因果效应。"
)

TEXTS[205] = (
    "S3在日间限行条件下重新优化配送中心启用、门店分配、车型选择及车辆路径。三组随机种子经有向2-opt"
    "处理后的日总成本分别为9,643.12元、9,653.98元和9,628.42元，平均为9,641.84元/日，样本标准差为"
    "12.83元/日；平均总里程为3,026.21 km。与S2相比，S3平均成本降低约691.2元/日，降幅为6.69%，平均"
    "里程减少27.54%；与S1相比，S3平均成本降低354.20元/日，降幅为3.54%。三个随机种子均形成8条燃油车"
    "路径和25条新能源车路径，且均未启用候选中心。由于主算例下两类车型路径数量与基准方案相同，车辆固定"
    "使用成本均为7,990元/日，S3较S2的691.2元/日降幅全部来自里程能源成本下降（2,343.05→1,651.84元/日）。"
    "但该降幅并非全部来自“联合优化”：4.3节分解显示，GA输出阶段仅贡献88.03元/日，2-opt贡献603.18元/日，"
    "后者占87.3%。此外，不启用候选中心时D2日均装载约99.98 t，接近100 t/日能力上限，说明现有中心容量"
    "是紧约束，S3的路径重排是在该容量约束下实现的。"
)

TEXTS[206] = (
    "在候选配送中心启用成本敏感性分析中，选取主算例三组随机种子中最终成本最低的方案（随机种子"
    "20263041），固定其遗传算法门店排列，对C1—C4的16种启用组合逐一重新解码并执行有向2-opt。结果显示："
    "在1,000元/中心·日下，不启用新增中心的条件成本最低，为9,628.42元/日；单独启用C1、C2、C3、C4的"
    "条件总成本分别为10,553.77、10,512.48、10,531.29和10,500.48元/日，均高于不启用方案；同时启用全部"
    "4个候选中心可将运输（固定+能源）成本由9,628.42元降至8,725.08元（减少903.34元），但需支付4,000元/日"
    "启用成本，净成本为12,725.08元/日，较不启用方案高3,096.66元/日。可见在1,000元/日下，候选中心的"
    "取舍是经济性权衡而非选址不可行。进一步改变单个候选中心日启用成本，固定排列条件下的持平点约为"
    "277.57元/中心·日；该阈值仅适用于固定GA排列及相应解码/2-opt结果，不是完整LRP的全局阈值。"
)

TEXTS[207] = (
    "为进一步检验低设施成本下候选中心启用的可能性，在候选中心日启用成本为200元的条件下，以随机种子"
    "20263041、种群规模20和最大迭代30代重新运行算法，得到启用C2、C3、C4的可行方案，日总成本为"
    "9,410.20元，总里程为1,944.87 km，共形成32条路径，其中燃油车7条、新能源车25条；全部568家门店均"
    "得到唯一服务，车辆数量、配送中心容量、道路可达性、车辆载重及新能源车里程约束均通过核验。该解较"
    "主算例少使用1辆燃油车，车辆固定成本由7,990元/日降至7,710元/日（低280元/日），同时支付600元/日"
    "候选中心启用成本；其与不启用方案的差额是“路径缩短+少用1辆燃油车−设施启用成本”的净结果，不能全部"
    "归因于候选中心。以同一最佳种子的不启用方案9,628.42元/日为基准，200元重算的持平阈值约为272.74元/"
    "中心·日；若以三种子均值9,641.84元/日为参照，则约为277.21元/中心·日。两者与固定排列条件阈值"
    "277.57元/中心·日接近，差异来自基准解与搜索路径不同。200元/日同样为敏感性假设，并非企业实际设施"
    "成本。"
)

TEXTS[209] = (
    "注：三组车队数量均为算例假设，总车辆数均为33辆；S3成本为3组随机种子运行均值。12辆燃油车+21辆"
    "新能源车方案的S3平均结果实际使用11条燃油车路径和21条新能源车路径，其余两组S3均使用各自假设的"
    "全部车辆。12F+21N的S3成本10,207.99元/日仍高于8F+25N的9,641.84元/日，其10.09%的较大降幅主要来自"
    "该配置下S2基准更高（11,352.97元/日），不能据此认为增加燃油车更优。上述结果用于比较车队结构变化"
    "对模型成本的影响，不代表企业真实车队配置或实际运营成本。"
)

TEXTS[210] = (
    "图12给出了固定最佳遗传算法排列条件下，候选配送中心启用成本变化对条件最优方案的影响。随着单个"
    "候选中心日启用成本提高，条件最优方案由启用C1—C4逐步转为启用C2、C3和C4，并最终转为不启用候选"
    "中心；固定排列条件下的持平点约为277.57元/中心·日。该阈值不是完整LRP的全局阈值；200元/日独立"
    "重算的持平点约为272.74元/中心·日（以同一最佳种子不启用方案为基准）。"
)

TEXTS[213] = (
    "为展示联合优化方案的空间服务结构，选取三组随机种子中成本最低的可行解（随机种子20263041）进行"
    "可视化。该解中，D1由燃油车服务140家门店、由新能源车服务31家门店，合计约44.50 t；D2由新能源车"
    "服务397家门店，合计约99.94 t，接近100 t/日能力上限；主算例未启用C1—C4。图13展示门店服务中心"
    "归属与车型配置，不绘制实际道路轨迹，因此不能将其解释为导航路径图。"
)

TEXTS[218] = (
    "注：有限OD比例按全部574个节点有序OD对（含对角零距离对）统计，不代表门店覆盖率。燃油货车日间"
    "矩阵的有限OD比例为21.41%，对应门店层面255/568=44.9%可由燃油货车从两个现有中心往返服务；符合"
    "条件纯电动货车矩阵在本算例中保持全部节点对连通。该全连通结果部分是矩阵未编码第三条三个严管片区"
    "对中型纯电动货车全日禁行的结果，不应解释为所有实际道路均对新能源车开放。"
)

TEXTS[220] = (
    "第一，坐标精度仍是重要限制。当前模型有304家门店保留原始坐标，原始坐标参考系未独立确认；另有"
    "18家采用低精度救援坐标、2家采用临时救援坐标。道路接入审计中19个节点标记为“需人工复核”，另有"
    "62个节点为低质量接入，5条拓扑修复连接中4条长度超过100 m。故本文构建的路网矩阵虽可用于计算，但"
    "尚不能表述为所有节点均已完成人工地理核验；上述节点对成本结果的影响应在坐标核验后重新检验。"
)

TEXTS[221] = (
    "第二，政策GIS边界属于近似构造，且覆盖不完整。二环线和三环线范围由OSM道路几何及凸包近似识别，"
    "桥梁、隧道和特殊区域规则按可识别字段简化。当前矩阵编码了二环线7:00—22:00禁行及可识别桥隧规则，"
    "但未逐路段编码第三条三个全日严管片区、第四条(二)—(九)八个7:00—22:00分片区、第五条城市货车通道、"
    "第六条金山大道、第七至十条中型及以上车辆限制及第十一条老旧柴油货车限制。三个严管片区位于二环内，"
    "其日间禁行已被二环规则近似覆盖，未编码主要影响22:00—次日7:00；第四条(二)—(九)多位于二环外，"
    "未编码会高估这些片区的燃油日间可达性；第三条三个片区对本文4.5 t中型纯电动货车同样全日禁行，矩阵"
    "未编码该规则，故新能源车在三个片区的可达性也可能被高估；第五条货车通道未编码则可能低估燃油可达性。"
    "因此，矩阵误差的净方向不确定，3.37%和6.69%应理解为该部分编码矩阵下的算例结果，而非政策效应的"
    "无偏估计。"
)

TEXTS[222] = (
    "第三，需求、车队及成本参数具有假设性。门店日需求总量144.447 t为均匀分布模拟值，并非企业订单"
    "记录；主算例8辆燃油车和25辆新能源车，以及5+28、12+21两组敏感性车队规模均为模型假设，并非企业"
    "实际车辆清单。车辆载重、固定使用成本、单位距离能源成本、新能源车300 km路径里程上限、配送中心"
    "能力和候选中心1,000元/日启用成本均采用代表性参数；其中新能源车4.5 t为代表性有效载重，若按4.12 t"
    "计，8F+25N总载重143.0 t低于144.447 t，主算例不可行（至少需8F+26N），详见4.5第七点。由于缺少"
    "门店时间窗、服务时长、真实车辆运行记录和候选场地费用，本文不评价实测到达时间或企业实际成本。"
)

TEXTS[223] = (
    "第四，固定基准方案与优化结果均具有算例属性。S1和S2采用依据门店坐标排序及容量、可达性约束贪婪"
    "构造的共同基准路线，不是企业历史配送线路；S2基准在日间限行矩阵下构造，S1仅将同一路线代入无限行"
    "矩阵，故S2−S1是配对差异而非政策因果效应。S3结果为有限随机种子下的遗传算法启发式可行解，路径层"
    "局部搜索仅实施有向2-opt，不能据此证明全局最优；且S3−S2同时包含GA与2-opt，4.3节分解显示2-opt贡献"
    "约87.3%，故不能将6.69%整体归因于选址—路径联合优化。主算例在1,000元/日启用成本下未启用候选中心，"
    "低成本情景下的中心启用结果也取决于假设参数。因而本文结果用于揭示模型参数和情景设定下的配送网络"
    "调整规律，不应直接解释为企业已实现的实际成本节约。"
)

TEXTS[224] = (
    "第五，燃油货车日间矩阵的门店级可达性较低，需明确披露。在燃油货车日间限行矩阵下，574个节点中仅"
    "21.41%的有向OD对存在有限距离；568家门店中，255家（44.9%）可由燃油货车从两个现有配送中心往返"
    "可达，其余313家仅能由纯电动货车服务。在本文矩阵中，不存在仅燃油可达或两种车型均不可达的门店；"
    "但若编码第三条三个严管片区对4.5 t中型纯电动货车的全日禁行，部分位于严管片区的门店可能变为仅燃油"
    "可达或两种车型均不可达，需在补全矩阵后重新检验。这意味着本文8燃油+25纯电动的混合车队并非自由"
    "选择，燃油货车被硬性限制在255家门店范围内，S2与S3的成本结构与降幅显著受该碎片化影响。此外，"
    "不启用候选中心时D2日均装载约99.98 t，已接近100 t/日能力上限，现有中心容量是紧约束；这也是低成本"
    "下候选中心被启用的重要原因。"
)

TEXTS[225] = (
    "第六，坐标参考系敏感性尚未闭合。304家门店保留原始坐标且其参考系未独立确认。若假设这304家坐标为"
    "GCJ-02并反算为WGS84，单店平均偏移约589 m；重新进行K-means聚类后，4个理论候选中心位置较基准移动"
    "约5.0—12.8 km，簇内门店数亦相应变化。该检验只重算了候选中心位置，未用偏移后的门店坐标重建道路"
    "距离矩阵，也未重新求解S1—S3，因此不能据此判断其对主结果无影响。在主算例不启用候选中心的条件下，"
    "候选中心移动对S3的直接影响有限；但门店坐标偏移会改变门店至中心的最短路距离，其成本影响仍需在"
    "重建矩阵后检验。"
)

TEXTS[226] = (
    "第七，需求水平与有效载重边界。将门店需求整体缩放为0.90、0.95、1.00、1.05、1.10倍并重新求解。"
    "0.90、0.95、1.00倍需求下模型可行，S3较S2的成本降幅分别为7.17%、7.26%和6.69%，均未启用候选中心；"
    "1.05倍和1.10倍需求（151.669 t、158.892 t）下模型未找到可行解。1.05倍需求虽低于按4.5 t计算的"
    "名义总载重152.5 t，但同时受单车载重、33条路径上限、中心容量和300 km续航约束影响，不能简单归因于"
    "总载重不足；1.10倍需求则超过名义总载重。若按4.12 t的有效载重计算，8F+25N的总载重为143.0 t，低于"
    "基准需求144.447 t，主算例本身即不可行，至少需增加1辆新能源车（8F+26N，总载重147.12 t）。因此，"
    "本文将4.5 t定义为代表性假设，相关可行性结论仅适用于该假设；这也说明“车队载重能力”是需求增长和"
    "车型参数变化时的首要约束之一，但并非唯一约束。"
)

TEXTS[228] = (
    "本文以武汉市某连锁商超配送网络为研究对象，基于568家门店、2个现有配送中心和4个理论候选配送中心，"
    "构建由OSM路网生成的情景化有向距离矩阵，建立考虑货运限行、有限混合车队及候选中心启用决策的"
    "选址—路径模型，并采用“固定基准配对+重新优化”的三情景设计分离限行对既定方案的直接影响与重新优化"
    "效果。门店日需求为均匀分布模拟值，总量144.447 t；主算例假设8辆燃油货车和25辆纯电动货车。本文的"
    "边际贡献在于：将区域、车型、时段及桥隧差异化规则转化为可进入模型的有向可达性矩阵；通过共享基准"
    "路线的配对设计避免将基准差异与优化改善混为一谈；并通过GA/2-opt分解和候选中心启用成本敏感性，"
    "给出条件阈值型判据。"
)

TEXTS[229] = (
    "主算例结果表明：第一，同一固定基准方案在日间限行矩阵下成本增加337.01元/日（3.37%），总里程增加"
    "8.66%；由于固定成本不变，该增量全部来自能源成本，其中燃油车里程增加27.81%、新能源车里程增加"
    "3.05%，能源成本增加16.80%。第二，日间限行下重新优化使成本降至9,641.84元/日，较S2降低约691.2元/日"
    "（6.69%），较S1降低354.20元/日（3.54%）；但分解显示，GA输出阶段仅贡献88.03元/日（0.85%），"
    "有向2-opt贡献603.18元/日（相当于S2的5.84%），占S3−S2的87.3%。因此，6.69%的改善主要来自路径层"
    "局部搜索，不能整体归因于选址—路径联合优化，更不能归因于候选中心启用。第三，在候选中心日启用成本"
    "为1,000元时，模型未启用新增中心；不启用方案的D2日均装载约99.98 t，已接近100 t/日能力上限，说明"
    "现有中心容量是紧约束。候选中心的条件持平成本约为277.57元/中心·日（固定排列）或272.74元/中心·日"
    "（独立重算），显著低于1,000元/日的基准假设；在200元/日下模型启用C2、C3、C4，成本为9,410.20元/日、"
    "里程1,944.87 km、32条路径（7F+25N），但该解较主算例少1辆燃油车、固定成本低280元/日，其与不启用"
    "方案的差额不能全部归因于候选中心。"
)

TEXTS[230] = (
    "车队结构与设施成本敏感性进一步表明：5F+28N、8F+25N和12F+21N三种假设配置下，S3较S2的降幅分别为"
    "6.42%、6.69%和10.09%；但12F+21N的S3成本10,207.99元/日仍高于8F+25N的9,641.84元/日，且其S3实际"
    "使用11条燃油车路径，故10.09%的较大降幅主要来自该配置下S2基准更高，不能据此认为增加燃油车更优。"
    "候选中心的经济性取决于运输成本节约与设施启用成本的权衡：在1,000元/日下不启用，在约273—278元/"
    "中心·日附近达到条件持平，在200元/日下启用C2、C3、C4。上述阈值均为固定排列或单次重算条件下的条件"
    "阈值，不是完整LRP的全局阈值；设施成本、需求分布和车队结构变化都可能移动该阈值。"
)

TEXTS[231] = (
    "本文结果受以下边界约束：门店坐标参考系尚未完全核验，304家门店保留原始坐标；政策矩阵仅近似编码"
    "二环线及可识别桥隧，第三条三个严管片区和第四条(二)—(九)八个分片区未逐路段编码，燃油货车可达性"
    "可能被高估，中型纯电动货车在三个严管片区的可达性也可能被高估，同时第五条货车通道未编码可能低估"
    "燃油可达性，净方向不确定；需求、车队、载重及成本参数均为算例假设，其中新能源车4.5 t为代表性"
    "有效载重，若按4.12 t计，8F+25N总载重143.0 t低于144.447 t，主算例本身不可行，至少需8F+26N；"
    "S1/S2为构造基准而非企业历史线路，S3为有限随机种子下的启发式可行解，不构成全局最优证明。因此，"
    "本文的3.37%、6.69%和阈值结果应理解为特定矩阵与参数假设下的算例结果，不应直接解释为政策因果效应、"
    "企业已实现节约或真实场地可行性。后续研究应核验门店坐标与官方限行边界、补齐第四条(二)—(九)等条款"
    "的逐路段编码、获取企业真实车队与成本数据，并开展更大计算预算和算法对照实验。"
)

for idx, text in TEXTS.items():
    set_text(p[idx], text)

# Table 8 caption centered
p[193].alignment = WD_ALIGN_PARAGRAPH.CENTER

# ---------------------------------------------------------------- table replacements
candidate_rows = [
    ["候选中心编号", "经度/(°)", "纬度/(°)", "簇内门店数"],
    ["C1", "114.223079", "30.627046", "122"],
    ["C2", "114.269903", "30.570583", "231"],
    ["C3", "114.361936", "30.620137", "127"],
    ["C4", "114.375572", "30.500212", "88"],
]
replace_table(t_candidates, candidate_rows, [3.2, 4.2, 4.2, 3.2],
              font_size=9, header_size=9)

demand_rows = [
    ["统计指标", "数值"],
    ["门店数量", "568家"],
    ["单店日需求下限（设定）", "0.1 t"],
    ["单店日需求上限（设定）", "0.4 t"],
    ["单店日需求均值", "0.2543 t"],
    ["单店日需求标准差", "0.0844 t"],
    ["门店日需求总量", "144.447 t"],
    ["实际生成的最小需求", "0.101 t"],
    ["实际生成的最大需求", "0.400 t"],
]
replace_table(t_demand, demand_rows, [8.0, 6.0],
              font_size=9, header_size=9,
              aligns=[WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.CENTER])

dc_rows = [
    ["配送中心类型", "数量/个", "日服务能力/(t/日)", "固定启用成本/(元/日)"],
    ["现有配送中心D1、D2", "2", "100", "—"],
    ["候选配送中心C1—C4", "4", "60", "1,000"],
]
replace_table(t_dc, dc_rows, [5.0, 3.0, 4.2, 3.8],
              font_size=9, header_size=9)

policy_rows = [
    ["条款/限行对象", "时段", "燃油货车", "符合条件新能源车", "本文矩阵处理"],
    ["第一条：武汉长江大桥、江汉桥、武汉长江二桥、三环线内隧道",
     "全天", "禁止", "禁止", "编码：按可识别桥隧设置禁行边"],
    ["第二条：三环线内其他高架桥、跨江/河/湖桥梁",
     "全天", "禁止", "允许（车长≤6 m、总质量≤8 t的中型新能源厢式车）",
     "编码：桥隧规则简化，新能源按允许处理"],
    ["第三条：三个全日禁行严管片区",
     "全天；仅微型、轻型新能源车在9:00—16:00、20:00—次日6:00例外",
     "禁止",
     "禁止（仅微型、轻型厢式/封闭式车部分时段例外；本文4.5 t中型车不适用）",
     "表列示；矩阵未逐路段编码。三片区位于二环内，日间已被二环规则覆盖，未编码主要影响夜间；中型新能源车亦被全日禁行"],
    ["第四条(一)：二环线及以内区域",
     "7:00—22:00", "禁止", "允许（符合条件）",
     "编码：以OSM二环几何近似"],
    ["第四条(二)—(九)：八个分片区",
     "7:00—22:00", "禁止", "允许（符合条件；部分时段厢式车例外）",
     "未编码；多位于二环外，可能高估燃油日间可达性"],
    ["第五条：城市货车通道（新湖街、解放大道下延线等）",
     "—", "允许（指定通道）", "允许（指定通道）", "未编码；可能低估受限区域内燃油可达性"],
    ["第六条：金山大道（环湖路—九通路）",
     "全天", "禁止", "允许", "未编码"],
    ["第七至十条：左岸大道、沌口路、东风大道高架、车谷大道等",
     "全天或6:30—8:30、16:00—21:00", "中型及以上禁止", "中型及以上禁止",
     "未编码；本文5 t燃油车与4.5 t新能源车按中型车理解时可能受影响"],
    ["第十一条：老旧柴油货车（2014年1月1日前登记）",
     "全天（三环内）", "禁止", "不适用", "未编码；假设本文燃油车非老旧柴油车"],
]
replace_table(t_policy, policy_rows, [3.1, 1.9, 1.8, 2.9, 6.3],
              font_size=8.0, header_size=8.5,
              aligns=[WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.CENTER,
                      WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER,
                      WD_ALIGN_PARAGRAPH.LEFT])

conn_rows = [
    ["路网矩阵", "允许有向边数", "有限OD对比例", "不可达有序OD对数"],
    ["无限行矩阵", "534,502", "100.00%", "0"],
    ["燃油车日间限行矩阵", "452,891", "21.41%", "258,938"],
    ["符合条件新能源车矩阵", "533,167", "100.00%", "0"],
]
new_conn = replace_table(t_conn, conn_rows, [5.0, 3.2, 3.2, 3.6],
                         font_size=9, header_size=9)

# ---------------------------------------------------------------- table captions
add_caption_before_table(t_cost, "表9 主算例三情景的配送成本与路径结果")
add_caption_before_table(new_conn, "表11 不同路网矩阵的可达性统计")

# ---------------------------------------------------------------- Figure 10
fig_p = p195.insert_paragraph_before()
fig_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
fig_p.paragraph_format.first_line_indent = None
fig_p.paragraph_format.space_before = Pt(6)
fig_p.paragraph_format.space_after = Pt(3)
fig_p.add_run().add_picture(FIG10, width=Cm(15.2))

cap_p = p195.insert_paragraph_before()
cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
cap_p.paragraph_format.first_line_indent = None
cap_p.paragraph_format.space_before = Pt(0)
cap_p.paragraph_format.space_after = Pt(6)
r = cap_p.add_run("图10 三种情景的比较逻辑与成本分解")
set_run_font(r, "宋体", 10.5, bold=False)

# ---------------------------------------------------------------- English abstract block
# CLC line
clc = p3.insert_paragraph_before()
clc.alignment = WD_ALIGN_PARAGRAPH.LEFT
clc.paragraph_format.first_line_indent = None
clc.paragraph_format.space_before = Pt(6)
clc.paragraph_format.space_after = Pt(6)
r = clc.add_run("中图分类号：F252.1；U491.1　　文献标识码：A")
set_run_font(r, "宋体", 10.5, bold=False)

# English title
et = p3.insert_paragraph_before()
et.alignment = WD_ALIGN_PARAGRAPH.CENTER
et.paragraph_format.first_line_indent = None
et.paragraph_format.space_before = Pt(10)
et.paragraph_format.space_after = Pt(6)
r = et.add_run("Delivery Routing and Distribution Center Activation Thresholds for an Urban "
               "Supermarket Chain under Freight Restriction Policies: A Case Study of Wuhan")
set_run_font(r, "Times New Roman", 14, bold=True)

# English abstract
ea = p3.insert_paragraph_before()
ea.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
ea.paragraph_format.first_line_indent = None
ea.paragraph_format.space_before = Pt(0)
ea.paragraph_format.space_after = Pt(6)
ea.paragraph_format.line_spacing = 1.15
r1 = ea.add_run("Abstract: ")
set_run_font(r1, "Times New Roman", 10.5, bold=True)
r2 = ea.add_run(
    "Freight restriction policies reshape road accessibility, fleet composition and distribution-center "
    "(DC) deployment in urban delivery networks. Taking a Wuhan supermarket chain with 568 stores, two "
    "existing DCs and four candidate DCs as a case, this paper converts area-, vehicle-, time- and "
    "bridge/tunnel-specific restrictions into scenario-based directed accessibility matrices, and "
    "formulates a location-routing model with a finite mixed fleet and binary DC activation decisions. "
    "A three-scenario design is used: an unrestricted fixed benchmark (S1), a daytime-restricted fixed "
    "benchmark using the same store assignment, vehicle types and visit sequence (S2), and a "
    "daytime-restricted re-optimization (S3) solved by a genetic algorithm (GA) followed by directed "
    "2-opt. The same benchmark plan costs 337.01 CNY/day (3.37%) more under daytime restrictions. "
    "Re-optimization reduces cost by about 691.2 CNY/day (6.69%) relative to S2 and by 354.20 CNY/day "
    "(3.54%) relative to S1. Decomposition shows that the GA contributes only 88.03 CNY/day (0.85%), "
    "whereas directed 2-opt contributes 603.18 CNY/day (5.84% of the S2 cost), accounting for 87.3% of "
    "the S3-S2 gap; the 6.69% gain should therefore not be attributed to DC activation or to joint "
    "location-routing decisions as a whole. At an activation cost of 1,000 CNY/DC/day, no candidate DC "
    "is opened. The conditional break-even cost is about 277.57 CNY/DC/day under a fixed permutation and "
    "272.74 CNY/DC/day in an independent rerun; at 200 CNY/DC/day, three candidate DCs are opened, but "
    "the solution uses 7 fuel and 25 electric routes and saves 280 CNY/day in vehicle fixed cost. The "
    "matrix only partially encodes the policy: the Second Ring Road and identifiable bridges/tunnels are "
    "approximated, while the three all-day strict zones and the remaining eight sub-areas of Article 4 "
    "are not encoded segment by segment. Fuel-vehicle accessibility, and medium electric-vehicle "
    "accessibility in the three strict zones, may therefore be overstated. The results are case-specific "
    "estimates under the stated matrix and parameter assumptions, not causal policy effects or global "
    "optima."
)
set_run_font(r2, "Times New Roman", 10.5, bold=False)

# English keywords
ek = p3.insert_paragraph_before()
ek.alignment = WD_ALIGN_PARAGRAPH.LEFT
ek.paragraph_format.first_line_indent = None
ek.paragraph_format.space_before = Pt(0)
ek.paragraph_format.space_after = Pt(10)
ek.paragraph_format.line_spacing = 1.15
r1 = ek.add_run("Keywords: ")
set_run_font(r1, "Times New Roman", 10.5, bold=True)
r2 = ek.add_run(
    "freight restriction policy; location-routing problem; mixed fleet; electric vehicle; directed "
    "accessibility matrix; genetic algorithm; distribution center activation threshold"
)
set_run_font(r2, "Times New Roman", 10.5, bold=False)

# ---------------------------------------------------------------- data/code statement
ds = p232.insert_paragraph_before()
ds.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
ds.paragraph_format.first_line_indent = Pt(21)
ds.paragraph_format.space_before = Pt(6)
ds.paragraph_format.space_after = Pt(6)
ds.paragraph_format.line_spacing = 1.25
r = ds.add_run(
    "数据与代码可用性声明：本文道路数据来自OpenStreetMap/Geofabrik公开数据；门店坐标、需求及企业相关"
    "数据为脱敏或模拟数据，受数据协议限制不公开；求解代码、输入快照及结果汇总可在通讯作者许可后按合理"
    "请求提供。"
)
set_run_font(r, "宋体", 10.5, bold=False)

# ---------------------------------------------------------------- move Table 10 after Figure 12
# Original order: candidate-cost paragraphs -> Table 10 -> Figure 12 -> Figure 13.
# Logical order: candidate-cost paragraphs -> Figure 12 -> fleet table -> Figure 13.
p_fig12_cap._p.addnext(p_t10_note._p)
p_fig12_cap._p.addnext(t_fleet._tbl)
p_fig12_cap._p.addnext(p_t10_cap._p)

lead = p_t10_cap.insert_paragraph_before()
lead.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
lead.paragraph_format.first_line_indent = Pt(21)
lead.paragraph_format.space_before = Pt(0)
lead.paragraph_format.space_after = Pt(0)
lead.paragraph_format.line_spacing = 1.25
r = lead.add_run(
    "车队结构同样影响三情景的成本差异。表10给出5F+28N、8F+25N和12F+21N三种假设配置下的成本结果："
    "三种配置下S3较S2的降幅分别为6.42%、6.69%和10.09%，但12F+21N的S3成本10,207.99元/日仍高于"
    "8F+25N的9,641.84元/日，且其S3实际使用11条燃油车路径。可见10.09%的较大降幅主要来自该配置下"
    "S2基准更高，不能据此认为增加燃油车更优。"
)
set_run_font(r, "宋体", 10.5, bold=False)

# ---------------------------------------------------------------- header
hdr = doc.sections[0].header.paragraphs[0]
set_text(hdr, "货运限行政策下城市商超配送路径优化与配送中心启用阈值研究")

# ---------------------------------------------------------------- save
doc.save(TMP)
print("saved temp:", TMP)
