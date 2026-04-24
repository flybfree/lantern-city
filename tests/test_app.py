from __future__ import annotations

from lantern_city.active_slice import ActiveSlice
from lantern_city.app import LanternCityApp
from lantern_city.engine import EngineOutcome
from lantern_city.response import compose_response


def test_talk_to_npc_surfaces_pre_case_clue_as_new_lead(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"
    app = LanternCityApp(database_path)
    app.start_new_game()
    app.enter_district("district_old_quarter")

    city = app._require_city()
    working_set = app._load_position()
    district = app._district("district_old_quarter")
    npc = app._npc("npc_shrine_keeper")
    clue = app.store.load_object("ClueState", "clue_missing_maintenance_line")

    assert working_set is not None
    assert district is not None
    assert npc is not None
    assert clue is not None

    latent_hint_clue = clue.model_copy(update={"related_case_ids": ["case_latent_hint"]})

    monkeypatch.setattr(LanternCityApp, "_peek_npc_case_hook", lambda self, npc_id: (None, None))

    def fake_handle_player_request(*args, **kwargs) -> EngineOutcome:
        return EngineOutcome(
            intent="talk_to_npc",
            active_slice=ActiveSlice(
                city=city,
                working_set=working_set,
                district=district,
                location=None,
                scene=None,
                npcs=[npc],
                clues=[latent_hint_clue],
                case=None,
            ),
            response=compose_response(
                narrative_text="Ila Venn lowers her voice and points out a detail that should not be easy to explain.",
                learned=["Notable clue: Maintenance records were altered after the outage."],
                visible_npcs=[npc.name],
                case_relevance=[
                    "New lead: This clue feels significant, even though you do not yet know what case it belongs to.",
                    "Clue reliability: credible",
                    "Lantern condition: dim",
                ],
                next_actions=["Ask a narrower question"],
            ),
            changed_objects=[],
        )

    monkeypatch.setattr("lantern_city.app.handle_player_request", fake_handle_player_request)

    output = app.talk_to_npc("npc_shrine_keeper", "Ask what seems wrong here.")

    assert "[New lead]" in output
    assert "What you learned:" in output
    assert "Notable clue: Maintenance records were altered after the outage." in output


def test_inspect_location_surfaces_pre_case_clue_as_new_lead(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"
    app = LanternCityApp(database_path)
    app.start_new_game()
    app.enter_district("district_old_quarter")

    city = app._require_city()
    working_set = app._load_position()
    district = app._district("district_old_quarter")
    location = app.store.load_object("LocationState", "location_archive_steps")
    clue = app.store.load_object("ClueState", "clue_missing_maintenance_line")

    assert working_set is not None
    assert district is not None
    assert location is not None
    assert clue is not None

    latent_hint_clue = clue.model_copy(
        update={"related_case_ids": ["case_latent_hint"], "related_npc_ids": []}
    )

    def fake_handle_player_request(*args, **kwargs) -> EngineOutcome:
        return EngineOutcome(
            intent="inspect_location",
            active_slice=ActiveSlice(
                city=city,
                working_set=working_set,
                district=district,
                location=location,
                scene=None,
                npcs=[],
                clues=[latent_hint_clue],
                case=None,
            ),
            response=compose_response(
                narrative_text="The marks on the archive steps line up too neatly to be wear.",
                learned=["Notable clue: Someone maintained this route after it should have gone dark."],
                notable_objects=["Fresh scoring in the stone"],
                case_relevance=[
                    "New lead: This clue feels significant, even though you do not yet know what case it belongs to.",
                    "Clue reliability: credible",
                    "Lantern condition: dim",
                ],
                next_actions=["Review known clues"],
            ),
            changed_objects=[],
        )

    monkeypatch.setattr("lantern_city.app.handle_player_request", fake_handle_player_request)

    output = app.inspect_location("location_archive_steps")

    assert "[Clue found:" in output
    assert "[New lead]" in output
    assert "Someone maintained this route after it should have gone dark." in output
