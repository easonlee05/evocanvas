from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path("/Users/apple/Desktop/evocanvas")
OUTPUT = ROOT / "output/pdf/huzhou-longemont-family-guide.pdf"
IMG_DIR = ROOT / "tmp/longemont-images"


def build_styles():
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CnTitle",
            fontName="STSong-Light",
            fontSize=24,
            leading=30,
            textColor=colors.HexColor("#143642"),
            alignment=TA_CENTER,
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CnSubTitle",
            fontName="STSong-Light",
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#4A6572"),
            alignment=TA_CENTER,
            spaceAfter=16,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CnHeading",
            fontName="STSong-Light",
            fontSize=16,
            leading=22,
            textColor=colors.HexColor("#0C4A60"),
            spaceBefore=4,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CnBody",
            fontName="STSong-Light",
            fontSize=10.5,
            leading=17,
            textColor=colors.HexColor("#222222"),
            alignment=TA_LEFT,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CnSmall",
            fontName="STSong-Light",
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#555555"),
            alignment=TA_LEFT,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CnCaption",
            fontName="STSong-Light",
            fontSize=8.8,
            leading=13,
            textColor=colors.HexColor("#5C6770"),
            alignment=TA_LEFT,
            spaceAfter=4,
        )
    )
    return styles


def section_title(text, styles):
    return [
        Spacer(1, 0.2 * cm),
        Paragraph(text, styles["CnHeading"]),
        HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#B7CCD6")),
        Spacer(1, 0.18 * cm),
    ]


def info_table(styles):
    data = [
        ["行程定位", "两天一夜，实际按一天半来玩，节奏宽松，不赶项目。"],
        ["住宿条件", "入住龙之梦钻石酒店，酒店票含大马戏。"],
        ["带娃原则", "上午安排主项目，下午尽量轻，保留午睡。"],
        ["三选一结论", "优先选动物世界步行区；不建议再额外塞演艺城。"],
    ]
    table = Table(data, colWidths=[3.1 * cm, 12.9 * cm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEADING", (0, 0), (-1, -1), 15),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF4F6")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0C4A60")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#222222")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7D7DE")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def timeline_table(styles):
    data = [
        ["Day 1", "12:00-14:00", "到酒店、办入住、吃午饭。尽量不额外赶景点。"],
        ["Day 1", "14:00-16:30", "回房休息，给孩子午睡。大人也顺便补体力。"],
        ["Day 1", "17:30-18:30", "提前吃晚饭，避免看马戏前手忙脚乱。"],
        ["Day 1", "18:30-19:00", "慢慢去大马戏，早点进场更从容。"],
        ["Day 2", "08:00-09:00", "酒店早餐，收拾轻装出门。"],
        ["Day 2", "09:30-12:00", "动物世界步行区，只抓孩子最感兴趣的一段，不求刷全。"],
        ["Day 2", "12:00-13:30", "回酒店附近吃午饭，优先就近解决。"],
        ["Day 2", "13:30-16:00", "午睡或安静休息。返程早的话，这里直接收尾。"],
        ["Day 2", "16:00以后", "按返程时间决定是轻松逛一小会儿，还是直接返程。"],
    ]
    table = Table(data, colWidths=[2.1 * cm, 3.1 * cm, 10.8 * cm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.6),
                ("LEADING", (0, 0), (-1, -1), 14),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C4A60")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FAFCFD")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FAFCFD"), colors.HexColor("#F1F7F9")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7D7DE")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    header = Table(
        [["日期", "时间", "安排"]],
        colWidths=[2.1 * cm, 3.1 * cm, 10.8 * cm],
    )
    header.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.8),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0C4A60")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return [header, table]


def image_block(path, caption, width_cm, styles):
    img = Image(str(path))
    img._restrictSize(width_cm * cm, 7.6 * cm)
    return [img, Spacer(1, 0.12 * cm), Paragraph(caption, styles["CnCaption"])]


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(colors.HexColor("#6A7B86"))
    canvas.drawRightString(A4[0] - 1.6 * cm, 1.0 * cm, f"{doc.page}")
    canvas.restoreState()


def build():
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.4 * cm,
        title="湖州龙之梦宽松亲子攻略",
        author="OpenAI Codex",
    )

    story = []

    story.append(Spacer(1, 1.0 * cm))
    story.append(Paragraph("湖州龙之梦宽松亲子攻略", styles["CnTitle"]))
    story.append(
        Paragraph(
            "适用前提：入住龙之梦钻石酒店、酒店票含大马戏、带小孩、下午尽量少安排并保留午睡。",
            styles["CnSubTitle"],
        )
    )
    story.append(info_table(styles))
    story.append(Spacer(1, 0.35 * cm))
    story.append(
        Paragraph(
            "一句话版本：这趟不要把自己玩成赶场。白天只保留一个主项目，上午去动物世界步行区，"
            "中午回酒店附近吃饭，下午午睡，晚上稳稳看大马戏。",
            styles["CnBody"],
        )
    )

    story.extend(section_title("为什么选动物世界步行区", styles))
    for line in [
        "你们已经有大马戏，晚上演艺类内容已经够了，白天再去演艺城会重复。",
        "动物世界步行区最适合带娃，互动感更强，节奏也最好控制，随时能停下来休息。",
        "冰雪世界虽然新鲜，但换装、低温、潮湿和排队会更折腾，不适合作为这次宽松版主线。",
        "如果孩子临场状态一般，就坚持一个原则：看到最喜欢的几段就撤，不追求刷全园。",
    ]:
        story.append(Paragraph(f"• {line}", styles["CnBody"]))

    story.extend(section_title("宽松时间线", styles))
    story.extend(timeline_table(styles))

    story.extend(section_title("最顺路的走法", styles))
    for line in [
        "Day 1 只办三件事：入住、休息、看大马戏。",
        "Day 2 只办一件大事：上午去动物世界步行区。",
        "中午以后就往酒店方向收，不要再开新副本，午睡比多刷一个项目更值。",
        "吃饭优先选酒店内或酒店周边就近解决，不建议为了打卡餐厅专门折返。",
    ]:
        story.append(Paragraph(f"• {line}", styles["CnBody"]))

    story.extend(section_title("带娃实用提醒", styles))
    for line in [
        "上午包里带好水、湿巾、小零食、防晒和一件薄外套。",
        "大马戏尽量提前进场，带小孩时最怕临开场找座、上厕所、买水同时发生。",
        "午睡如果没睡成，下午也尽量保持安静活动，不要再进耗体力项目。",
        "返程日的目标是顺利收尾，不是把票价玩回本。",
    ]:
        story.append(Paragraph(f"• {line}", styles["CnBody"]))

    story.append(PageBreak())
    story.append(Paragraph("公开实拍参考图", styles["CnHeading"]))
    story.append(
        Paragraph(
            "下面三张是当前可公开访问的龙之梦相关实拍图，主要用来帮助你快速建立场景感："
            "动物世界、夜景氛围和演艺舞台。",
            styles["CnSmall"],
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.extend(
        image_block(
            IMG_DIR / "animal_world_2.jpg",
            "图 1：动物世界实拍。适合放在第二天上午，孩子有精神时去看。",
            16.5,
            styles,
        )
    )
    story.append(Spacer(1, 0.28 * cm))
    row = Table(
        [
            [
                Image(str(IMG_DIR / "candidate2.jpg"), width=8.0 * cm, height=4.8 * cm),
                Image(str(IMG_DIR / "candidate3.jpg"), width=8.0 * cm, height=4.8 * cm),
            ]
        ],
        colWidths=[8.1 * cm, 8.1 * cm],
    )
    row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(row)
    story.append(Spacer(1, 0.12 * cm))
    story.append(
        Paragraph(
            "图 2-3：公开演艺/夜景参考。你们这次已经含大马戏，晚上保留一个重头项目就够了。",
            styles["CnCaption"],
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        Paragraph(
            "公开图片来源："
            '<link href="https://www.trip.com/travel-guide/attraction/changxing/longemont-animal-world-83582734/" color="blue">Trip.com Longemont Animal World</link>；'
            '<link href="https://gs.ctrip.com/html5/you/sight/changxing1832/5034353.html" color="blue">携程 太湖龙之梦乐园</link>；'
            '<link href="https://you.ctrip.com/sight/changxing1832/5716805.html" color="blue">携程 醉美太湖演出</link>。',
            styles["CnSmall"],
        )
    )

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)


if __name__ == "__main__":
    build()
