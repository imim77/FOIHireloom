import unicodedata

from FOIHireloom.dto.county import CountyDefinitionDTO


class CroatianCountyCatalog:
    """Stable application codes; RSS resource numbering is not a county code."""

    definitions = tuple(
        CountyDefinitionDTO(code=code, name=name)
        for code, name in (
            ("bjelovarsko-bilogorska", "Bjelovarsko-bilogorska županija"),
            ("brodsko-posavska", "Brodsko-posavska županija"),
            ("dubrovacko-neretvanska", "Dubrovačko-neretvanska županija"),
            ("grad-zagreb", "Grad Zagreb"),
            ("istarska", "Istarska županija"),
            ("karlovacka", "Karlovačka županija"),
            ("koprivnicko-krizevacka", "Koprivničko-križevačka županija"),
            ("krapinsko-zagorska", "Krapinsko-zagorska županija"),
            ("licko-senjska", "Ličko-senjska županija"),
            ("medimurska", "Međimurska županija"),
            ("osjecko-baranjska", "Osječko-baranjska županija"),
            ("pozesko-slavonska", "Požeško-slavonska županija"),
            ("primorsko-goranska", "Primorsko-goranska županija"),
            ("sisacko-moslavacka", "Sisačko-moslavačka županija"),
            ("splitsko-dalmatinska", "Splitsko-dalmatinska županija"),
            ("sibensko-kninska", "Šibensko-kninska županija"),
            ("varazdinska", "Varaždinska županija"),
            ("viroviticko-podravska", "Virovitičko-podravska županija"),
            ("vukovarsko-srijemska", "Vukovarsko-srijemska županija"),
            ("zadarska", "Zadarska županija"),
            ("zagrebacka", "Zagrebačka županija"),
        )
    )

    def __init__(self) -> None:
        self._by_label = {self.normalise(county.name): county for county in self.definitions}

    @staticmethod
    def normalise(label: str) -> str:
        label = label.casefold().replace("đ", "d").replace("–", "-").replace("—", "-")
        label = "".join(char for char in unicodedata.normalize("NFKD", label) if not unicodedata.combining(char))
        return " ".join(label.split()).replace(" - ", "-").removesuffix(" zupanija")

    def match(self, label: str) -> CountyDefinitionDTO | None:
        return self._by_label.get(self.normalise(label))

    def is_eu(self, label: str) -> bool:
        return self.normalise(label) in {"poslovi u eu", "eu", "europska unija"}
