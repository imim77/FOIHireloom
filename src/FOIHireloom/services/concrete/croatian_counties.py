import unicodedata

from FOIHireloom.dto.county import CountyDefinitionDTO


class CroatianCountyCatalog:
    """Stable application codes; RSS resource numbering is not a county code.

    iso_code is the county's ISO 3166-2:HR code, which links other sources,
    such as DZS tables, to the same county.
    """

    definitions = tuple(
        CountyDefinitionDTO(code=code, iso_code=iso_code, name=name)
        for code, iso_code, name in (
            ("bjelovarsko-bilogorska", "HR-07", "Bjelovarsko-bilogorska županija"),
            ("brodsko-posavska", "HR-12", "Brodsko-posavska županija"),
            ("dubrovacko-neretvanska", "HR-19", "Dubrovačko-neretvanska županija"),
            ("grad-zagreb", "HR-21", "Grad Zagreb"),
            ("istarska", "HR-18", "Istarska županija"),
            ("karlovacka", "HR-04", "Karlovačka županija"),
            ("koprivnicko-krizevacka", "HR-06", "Koprivničko-križevačka županija"),
            ("krapinsko-zagorska", "HR-02", "Krapinsko-zagorska županija"),
            ("licko-senjska", "HR-09", "Ličko-senjska županija"),
            ("medimurska", "HR-20", "Međimurska županija"),
            ("osjecko-baranjska", "HR-14", "Osječko-baranjska županija"),
            ("pozesko-slavonska", "HR-11", "Požeško-slavonska županija"),
            ("primorsko-goranska", "HR-08", "Primorsko-goranska županija"),
            ("sisacko-moslavacka", "HR-03", "Sisačko-moslavačka županija"),
            ("splitsko-dalmatinska", "HR-17", "Splitsko-dalmatinska županija"),
            ("sibensko-kninska", "HR-15", "Šibensko-kninska županija"),
            ("varazdinska", "HR-05", "Varaždinska županija"),
            ("viroviticko-podravska", "HR-10", "Virovitičko-podravska županija"),
            ("vukovarsko-srijemska", "HR-16", "Vukovarsko-srijemska županija"),
            ("zadarska", "HR-13", "Zadarska županija"),
            ("zagrebacka", "HR-01", "Zagrebačka županija"),
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
