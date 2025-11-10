import re


class RegexFilter:
    def __init__(self, filter: str):
        self.filter = filter

    def apply(self, text: str):
        return re.sub(self.filter, '', text, flags=re.IGNORECASE).strip()

    @staticmethod
    def md_json():
        return RegexFilter(r"```json\s*|\s*```")

class FilteringString:
    def __init__(self, text: str):
        self.text = text

    def __str__(self):
        return str(self.text)

    def filter(self, filter: RegexFilter):
        self.text = filter.apply(self.text)
        return self
