"""Registry de providers de cotação por nome. 'manual' não entra aqui: é via --manual."""
from po.cotacoes.providers.yahoo import YahooProvider

REGISTRY = {"yahoo": YahooProvider}


def criar_provider(nome: str, buscar=None):
    if nome not in REGISTRY:
        raise ValueError(f"provider {nome!r} desconhecido (disponíveis: {sorted(REGISTRY)}; "
                         "'manual' é via --manual)")
    return REGISTRY[nome](buscar=buscar) if buscar is not None else REGISTRY[nome]()
