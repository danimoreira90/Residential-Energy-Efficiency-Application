"""RED contracts for the Article 27 schedule and reviewed Fio B snapshot."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from energia.tariff import gd

_FIO_B_RESOURCE_URL = (
    "https://dadosabertos.aneel.gov.br/pt_BR/dataset/componentes-tarifarias/"
    "resource/e8717aa8-2521-453f-bf16-fbb9a16eea39"
)


@pytest.mark.parametrize(
    ("year", "fraction"),
    [(2023, "0.15"), (2024, "0.30"), (2025, "0.45"), (2026, "0.60"),
     (2027, "0.75"), (2028, "0.90")],
)
def test_article_27_schedule_is_exact(year: int, fraction: str) -> None:
    charge = gd.compensation_charge(year)
    assert charge.fraction == Decimal(fraction)
    assert charge.regulatory_basis == "article_27_transition"


def test_schedule_rejects_pre_transition_and_labels_post_2028() -> None:
    with pytest.raises(gd.GDDataError):
        gd.compensation_charge(2022)
    charge = gd.compensation_charge(2029)
    assert charge.fraction == Decimal("1.00")
    assert charge.regulatory_basis == "conservative_post_2028_planning_scenario"


def _payload(value: str = "361.02479751700002") -> dict[str, object]:
    return {
        "source": {
            "resource_id": "e8717aa8-2521-453f-bf16-fbb9a16eea39",
            "resource_hash": "c4bd43306833b0583a2fad9fa0945665",
            "updated": "2026-09-03",
            "url": _FIO_B_RESOURCE_URL,
        },
        "unit": "BRL_per_MWh",
        "rows": [{
            "distributor": "ENEL RJ",
            "tariff_group": "B1",
            "modality": "Convencional",
            "consumer_class": "Residencial",
            "consumer_subclass": "Residencial",
            "consumer_detail": "Não se aplica",
            "tariff_period": "Não se aplica",
            "basis": "Tarifa de Aplicação",
            "component": "TUSD_FioB",
            "effective_from": "2026-03-15",
            "effective_to": "2027-03-14",
            "value": value,
        }],
    }


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_committed_fio_b_snapshot_is_exact_and_contains_no_pii() -> None:
    snapshot = gd.load_fio_b_snapshot()
    assert snapshot.distributor == "ENEL RJ"
    assert snapshot.tariff_group == "B1"
    assert snapshot.modality == "Convencional"
    assert snapshot.consumer_class == "Residencial"
    assert snapshot.consumer_subclass == "Residencial"
    assert snapshot.consumer_detail == "Não se aplica"
    assert snapshot.tariff_period == "Não se aplica"
    assert snapshot.basis == "Tarifa de Aplicação"
    assert snapshot.component == "TUSD_FioB"
    assert snapshot.unit == "BRL_per_MWh"
    assert snapshot.effective_from.isoformat() == "2026-03-15"
    assert snapshot.effective_to.isoformat() == "2027-03-14"
    assert snapshot.tusd_fio_b_brl_per_mwh == Decimal("361.02479751700002")
    assert snapshot.source.resource_id == "e8717aa8-2521-453f-bf16-fbb9a16eea39"
    assert snapshot.source.resource_hash == "c4bd43306833b0583a2fad9fa0945665"
    assert snapshot.source.url == _FIO_B_RESOURCE_URL
    module_file = gd.__file__
    assert module_file is not None
    raw = (Path(module_file).parent / "snapshots" / "enel_rj_fio_b.json").read_text(
        encoding="utf-8"
    )
    assert "NumCPFCNPJ" not in raw


def test_snapshot_deduplicates_only_identical_complete_rows(tmp_path: Path) -> None:
    payload = _payload()
    rows = payload["rows"]
    assert isinstance(rows, list) and isinstance(rows[0], dict)
    first_row = cast(dict[str, object], rows[0])
    payload["rows"] = [first_row, dict(first_row)]
    path = tmp_path / "same.json"
    _write(path, payload)
    assert gd.load_fio_b_snapshot(path).tusd_fio_b_brl_per_mwh == Decimal(
        "361.02479751700002"
    )


@pytest.mark.parametrize("mutation", ["conflict", "mismatch", "generic_url"])
def test_snapshot_fails_closed_on_conflict_or_mismatch(
    tmp_path: Path, mutation: str
) -> None:
    payload = _payload()
    rows = payload["rows"]
    assert isinstance(rows, list) and isinstance(rows[0], dict)
    first_row = cast(dict[str, object], rows[0])
    row = dict(first_row)
    if mutation == "conflict":
        row["value"] = "999.00"
        payload["rows"] = [first_row, row]
    elif mutation == "mismatch":
        row["component"] = "TUSD"
        payload["rows"] = [row]
    else:
        source = payload["source"]
        assert isinstance(source, dict)
        source["url"] = "https://dadosabertos.aneel.gov.br/"
    path = tmp_path / f"{mutation}.json"
    _write(path, payload)
    with pytest.raises(gd.GDDataError):
        gd.load_fio_b_snapshot(path)
