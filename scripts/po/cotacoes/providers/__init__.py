"""Registry de providers de cotação por nome. 'manual' não entra aqui: é via --manual."""
from po.cotacoes.providers.bcb_sgs import BcbSgsProvider
from po.cotacoes.providers.brapi import BrapiProvider
from po.cotacoes.providers.yahoo import YahooProvider

REGISTRY = {"yahoo": YahooProvider, "brapi": BrapiProvider, "bcb-sgs": BcbSgsProvider}


def criar_provider(nome: str, buscar=None, **kwargs):
    if nome not in REGISTRY:
        raise ValueError(f"provider {nome!r} desconhecido (disponíveis: {sorted(REGISTRY)}; "
                         "'manual' é via --manual)")
    if buscar is not None:
        kwargs["buscar"] = buscar
    return REGISTRY[nome](**kwargs)
