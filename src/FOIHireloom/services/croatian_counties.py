from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True)
class CountyDefinition:
    code: str
    name: str


class CroatianCountyCatalog:
    """Stable application codes; RSS resource numbering is not a county code."""

    definitions = (
        CountyDefinition("bjelovarsko-bilogorska", "Bjelovarsko-bilogorska županija"),
        CountyDefinition("brodsko-posavska", "Brodsko-posavska županija"),
        CountyDefinition("dubrovacko-neretvanska", "Dubrovačko-neretvanska županija"),
        CountyDefinition("grad-zagreb", "Grad Zagreb"),
        CountyDefinition("istarska", "Istarska županija"),
        CountyDefinition("karlovacka", "Karlovačka županija"),
        CountyDefinition("koprivnicko-krizevacka", "Koprivničko-križevačka županija"),
        CountyDefinition("krapinsko-zagorska", "Krapinsko-zagorska županija"),
        CountyDefinition("licko-senjska", "Ličko-senjska županija"),
        CountyDefinition("medimurska", "Međimurska županija"),
        CountyDefinition("osjecko-baranjska", "Osječko-baranjska županija"),
        CountyDefinition("pozesko-slavonska", "Požeško-slavonska županija"),
        CountyDefinition("primorsko-goranska", "Primorsko-goranska županija"),
        CountyDefinition("sisacko-moslavacka", "Sisačko-moslavačka županija"),
        CountyDefinition("splitsko-dalmatinska", "Splitsko-dalmatinska županija"),
        CountyDefinition("sibensko-kninska", "Šibensko-kninska županija"),
        CountyDefinition("varazdinska", "Varaždinska županija"),
        CountyDefinition("viroviticko-podravska", "Virovitičko-podravska županija"),
        CountyDefinition("vukovarsko-srijemska", "Vukovarsko-srijemska županija"),
        CountyDefinition("zadarska", "Zadarska županija"),
        CountyDefinition("zagrebacka", "Zagrebačka županija"),
    )

    def __init__(self) -> None:
        self._by_label = {self.normalise(county.name): county for county in self.definitions}

    @staticmethod
    def normalise(label: str) -> str:
        label = label.casefold().replace("đ", "d").replace("–", "-").replace("—", "-")
        label = "".join(char for char in unicodedata.normalize("NFKD", label) if not unicodedata.combining(char))
        return " ".join(label.split()).replace(" - ", "-").removesuffix(" zupanija")

    def match(self, label: str) -> CountyDefinition | None:
        return self._by_label.get(self.normalise(label))

    def is_eu(self, label: str) -> bool:
        return self.normalise(label) in {"poslovi u eu", "eu", "europska unija"}
