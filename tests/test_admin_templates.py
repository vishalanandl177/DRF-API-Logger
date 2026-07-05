from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


class AdminChartTemplateTests(SimpleTestCase):
    def test_each_changelist_chart_has_its_own_collapsible_loader(self):
        template = ROOT.joinpath(
            "drf_api_logger", "templates", "charts_change_list.html"
        ).read_text(encoding="utf-8")

        for chart_name in (
            "api-calls-by-day",
            "api-calls-by-status-code",
            "sql-queries-by-day",
        ):
            with self.subTest(chart_name=chart_name):
                self.assertIn(f'data-chart="{chart_name}"', template)
                self.assertIn(
                    f'data-chart-url="chart-data/{chart_name}/"', template
                )

        self.assertIn('aria-expanded="false"', template)
        self.assertIn('hidden', template)
        self.assertIn("loadChartData(card)", template)
        self.assertIn("fetch(chartUrl", template)
        self.assertIn("card.dataset.loaded = 'true';", template)

    def test_changelist_charts_do_not_embed_backend_datasets(self):
        template = ROOT.joinpath(
            "drf_api_logger", "templates", "charts_change_list.html"
        ).read_text(encoding="utf-8")

        self.assertNotIn("{% for item in analytics %}", template)
        self.assertNotIn("{{ status_code_count_keys }}", template)
        self.assertNotIn("{{ status_code_count_values }}", template)
        self.assertNotIn("{% for item in sql_distribution %}", template)

    def test_changelist_chart_cards_use_full_available_width(self):
        template = ROOT.joinpath(
            "drf_api_logger", "templates", "charts_change_list.html"
        ).read_text(encoding="utf-8")

        card_rule_start = template.find(".api-log-chart-card {")
        card_rule_end = template.find("}", card_rule_start)

        self.assertNotEqual(-1, card_rule_start)
        self.assertNotEqual(-1, card_rule_end)

        card_rule = template[card_rule_start:card_rule_end]
        self.assertIn("width: 100%;", card_rule)
        self.assertIn("box-sizing: border-box;", card_rule)
        self.assertNotIn("max-width", card_rule)

    def test_changelist_chart_panels_are_capped_to_200px_height(self):
        template = ROOT.joinpath(
            "drf_api_logger", "templates", "charts_change_list.html"
        ).read_text(encoding="utf-8")

        panel_rule_start = template.find(".api-log-chart-panel {")
        panel_rule_end = template.find("}", panel_rule_start)
        canvas_rule_start = template.find(".api-log-chart-panel canvas {")
        canvas_rule_end = template.find("}", canvas_rule_start)

        self.assertNotEqual(-1, panel_rule_start)
        self.assertNotEqual(-1, panel_rule_end)
        self.assertNotEqual(-1, canvas_rule_start)
        self.assertNotEqual(-1, canvas_rule_end)

        panel_rule = template[panel_rule_start:panel_rule_end]
        canvas_rule = template[canvas_rule_start:canvas_rule_end]

        self.assertIn("height: 200px;", panel_rule)
        self.assertIn("max-height: 200px;", panel_rule)
        self.assertIn("overflow: hidden;", panel_rule)
        self.assertIn("height: 200px !important;", canvas_rule)
        self.assertIn("max-height: 200px;", canvas_rule)
        self.assertNotIn("min-height", canvas_rule)
        self.assertEqual(2, template.count("maintainAspectRatio: false"))

    def test_changelist_graph_api_fetch_has_30_second_timeout(self):
        template = ROOT.joinpath(
            "drf_api_logger", "templates", "charts_change_list.html"
        ).read_text(encoding="utf-8")

        load_chart_data_start = template.find("function loadChartData(card)")
        render_charts_start = template.find("function showMessage")

        self.assertNotEqual(-1, load_chart_data_start)
        self.assertNotEqual(-1, render_charts_start)

        load_chart_data = template[load_chart_data_start:render_charts_start]
        self.assertIn("const graphApiTimeoutMs = 30000;", template)
        self.assertIn("const controller = new AbortController();", load_chart_data)
        self.assertIn(
            "setTimeout(() => controller.abort(), graphApiTimeoutMs)",
            load_chart_data,
        )
        self.assertIn("signal: controller.signal", load_chart_data)
        self.assertIn("clearTimeout(timeoutId)", load_chart_data)

    def test_changelist_charts_render_only_after_toggle_click(self):
        template = ROOT.joinpath(
            "drf_api_logger", "templates", "charts_change_list.html"
        ).read_text(encoding="utf-8")

        dom_ready_start = template.find("document.addEventListener('DOMContentLoaded'")
        render_charts_start = template.find("function renderCharts")

        self.assertNotEqual(-1, dom_ready_start)
        self.assertNotEqual(-1, render_charts_start)

        dom_ready_block = template[dom_ready_start:render_charts_start]

        self.assertIn("toggle.addEventListener('click'", dom_ready_block)
        self.assertNotIn("new Chart(", dom_ready_block)
