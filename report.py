import json
from reportlab.platypus.flowables import ListFlowable, ListItem
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4


def format_seconds_extended(seconds):
    total_seconds = int(seconds)

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds_remaining = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds_remaining:02d}"
    else:
        return f"{minutes:02d}:{seconds_remaining:02d}"

class Report:
    def __init__(self, result, audio_len_secs):
        self.result = result
        self.audio_len_secs = audio_len_secs

    def build_plot(self):
        try:
            susp = self.result["suspiscious_segments"]
            x = [x for x in range(1, self.audio_len_secs)]
            y = []

            cnt = 0
            refs = {}

            for i in range(1, 150):
              for t in susp:
                if i >= t['start'] and i <= t['end']:
                  y.append(1)

                  text_y = 1

                  if cnt % 2 != 0:
                    text_y = 0.75

                  plt.text(i, text_y, cnt)
                  cnt += 1
                  refs[cnt] = t
                  break
              else:
                y.append(0)

            plot = plt.plot(x, y)
            plt.xlabel("Время (с)")
            path = "/tmp/output.png"
            plt.savefig(path)

            fig = plt.gcf()
            size = fig.get_size_inches()*fig.dpi

            return {
                "image": path,
                "size": size,
                "refs": refs
            }

        except KeyError:
            return None

    def save_pdf(self):
        doc = SimpleDocTemplate("output.pdf", pagesize=A4)
        styles = getSampleStyleSheet()

        story = [
            Paragraph(f"Результат для {self.data["call_number"]}:", ParagraphStyle(parent=styles["Normal"], alignment=TA_CENTER, fontSize=16))
            Image("/tmp/output.png", width=size[0], height=size[1])
            ListFlowable([
                ListItem(Paragraph(f"Общее содержание: {self.data["summary"]}", styles["Normal"]))
                ListItem(Paragraph(f"Категория: {self.data["category"]}", styles["Normal"]))
                ListItem(Paragraph(f"Риск-скор: {self.data["rist_score"]}", styles["Normal"]))
                ListItem(Paragraph(f"Индикаторы: {", ".join(self.data["indicators"])}", styles["Normal"]))
            ])
        ]

        plot_data = self.build_plot()

        if plot_data == None:
            doc.build(story)
            return

        story.append(
            Paragraph("Подозрительные моменты:")
        )
        for k, v in plot_data["refs"].items():
            story.append(Paragraph(f"{k}", styles["Normal"]))
            story.append(
                ListFlowable([
                    ListItem(f"Тайминг: {format_seconds_extended(v["start"])}-{format_seconds_extended(v["end"])}", styles["Normal"])
                    ListItem(f"Цитата: {v["text"]}", styles["Normal"])
                    ListItem(f"Причина: {v["reason"]}", styles["Normal"])
                ])
            )

        doc.build(story)

    def save_json(self):
        s = json.dumps(self.result)

        with open("output.json", "wt") as f:
            f.write(s)
