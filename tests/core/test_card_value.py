from fantasyhoops.core import card_value, chart, profile


def test_the_value_and_comps_fill_is_one_entry_of_fills_and_the_modal_adds_it_once():
    assert card_value in profile.FILLS
    html = profile.modal()
    assert html.count(card_value.script()) == 1 and html.count(card_value.STYLE) == 1
    assert html.index("window.LabCard = ") < html.index(card_value.script())  # LabCard exists before the fills
    assert card_value.METHODS in profile.card_script()


def test_the_script_fills_only_the_value_and_comps_slots_with_the_shared_tooltip():
    s = card_value.script()
    assert "C.fill.value = " in s and "C.fill.comps = " in s
    assert "C.fill.role" not in s and "C.fill.cats" not in s
    assert s.count("C.bindTip(") == 2 and "lab-tt-" not in s  # the card text comes from profile.bindTip()
    assert '<tr class="lab-c-hit"' in s  # a tap on a comps row keeps its card


def test_the_methods_give_a_value_line_and_a_comps_line():
    assert "<li><b>Value.</b>" in card_value.METHODS and "<li><b>Comps.</b>" in card_value.METHODS


def test_the_style_has_no_inline_chart_sizes_no_tooltip_text_and_no_external_url():
    assert "stroke-width" not in card_value.STYLE and "http" not in card_value.script() + card_value.STYLE
    assert ".lab-tt" not in card_value.STYLE
    assert chart.RAW_COLOR.search(card_value.STYLE) is None
