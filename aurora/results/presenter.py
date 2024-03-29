from __future__ import annotations

import contextlib

from .model import ResultsModel
from .plot.factory import PlotPresenterFactory
from .plot.model import PlotModel
from .plot.presenter import PlotPresenter
from .plot.view import PlotView
from .view import ResultsView


class ResultsPresenter():
    """
    docstring
    """

    def __init__(
        self,
        model: ResultsModel,
        view: ResultsView,
    ) -> None:
        """docstring"""

        self.model = model
        self.view = view

        self._set_event_handlers()

        self.update_view_experiments()

    def update_view_experiments(self, _=None) -> None:
        """docstring"""

        self.view.group_selector.options = self.model.get_groups()

        self.model.update_experiments(
            group=self.view.group_selector.value,
            last_days=self.view.last_days.value,
            active_only=self.view.active_check.value,
        )

        options = self._build_experiment_selector_options()
        self.view.experiment_selector.options = options

    def toggle_plot_button(self, _=None) -> None:
        """docstring"""
        no_experiments = not self.view.experiment_selector.value
        no_plot_type = not self.view.plot_type_selector.value
        self.view.plot_button.disabled = no_experiments or no_plot_type

    def update_group_name_state(self, _=None) -> None:
        """docstring"""
        no_experiments = not self.view.experiment_selector.value
        self.view.group_name.disabled = no_experiments

    def toggle_group_name_button(self, _=None) -> None:
        """docstring"""
        self.view.group_add_button.disabled = not self.view.group_name.value

    def on_weights_file_change(self) -> None:
        """docstring"""
        with contextlib.suppress(Exception):
            filename = self.view.weights_filechooser.value
            self.model.fetch_weights(filename)
            self.view.weights_reset_button.disabled = not filename

    def on_plot_button_clicked(self, _=None) -> None:
        """docstring"""
        self.view.info.clear_output()
        if self._has_valid_selection():
            self.add_plot_view()

    def on_group_add_button_click(self, _=None) -> None:
        """docstring"""
        label = self.view.group_name.value
        experiments = self.view.experiment_selector.value
        self.model.create_new_group(label, experiments)
        self.update_view_experiments()
        self.view.group_name.value = ""

    def add_plot_view(self) -> None:
        """docstring"""

        experiment_ids = self.view.experiment_selector.value
        plot_label = self.view.plot_type_selector.label
        plot_type = self.view.plot_type_selector.value

        plot_view = PlotView()

        title = f"{plot_label} for experiment"
        title += "s" if len(experiment_ids) > 1 else ""
        title += f" {', '.join(str(id) for id in experiment_ids)}"

        plot_view.set_title(0, title)

        plot_model = PlotModel(self.model, experiment_ids)

        plot_presenter = PlotPresenterFactory.build(
            plot_label,
            plot_type,
            plot_model,
            plot_view,
        )

        if plot_presenter.closing_message:
            message = plot_presenter.closing_message
            self.display_info_message(message)
            return

        self.view.plots_container.children += (plot_view, )

        plot_presenter.observe(
            names="closing_message",
            handler=self.remove_plot_view,
        )

        plot_presenter.start()

    def remove_plot_view(self, trait: dict) -> None:
        """docstring"""

        plot_presenter: PlotPresenter = trait["owner"]

        if (message := trait["new"]) != "closed":
            self.display_info_message(message)

        if plot_presenter.view in self.view.plot_views:
            self.view.plots_container.children = [
                view for view in self.view.plot_views
                if view is not plot_presenter.view
            ]

        plot_presenter.unobserve(self.remove_plot_view)

    def display_info_message(self, message: str) -> None:
        """docstring"""

        with self.view.info:
            print(message)

    def toggle_widgets(self, _=None) -> None:
        """docstring"""
        self.toggle_plot_button()
        self.update_group_name_state()

    def schedule_monitor_kill_order(self, _=None) -> None:
        """docstring"""
        for eid in self.view.experiment_selector.value:
            self.model.schedule_monitor_kill_order(eid)
        self.update_view_experiments()

    def cancel_monitor_kill_order(self, _=None) -> None:
        """docstring"""
        for eid in self.view.experiment_selector.value:
            self.model.cancel_monitor_kill_order(eid)
        self.update_view_experiments()

    def _set_event_handlers(self) -> None:
        """docstring"""
        self.view.on_displayed(self.update_view_experiments)
        self.view.plot_button.on_click(self.on_plot_button_clicked)
        self.view.update_button.on_click(self.update_view_experiments)
        self.view.thumb_down.on_click(self.schedule_monitor_kill_order)
        self.view.thumb_up.on_click(self.cancel_monitor_kill_order)
        self.view.active_check.observe(self.update_view_experiments, "value")
        self.view.group_selector.observe(self.update_view_experiments, "value")
        self.view.last_days.observe(self.update_view_experiments, "value")
        self.view.experiment_selector.observe(self.toggle_widgets, "value")
        self.view.plot_type_selector.observe(self.toggle_plot_button, "value")
        self.view.weights_reset_button.on_click(self.reset_weights_file)
        self.view.group_name.observe(self.toggle_group_name_button, "value")
        self.view.group_add_button.on_click(self.on_group_add_button_click)
        self.view.weights_filechooser.register_callback(
            self.on_weights_file_change)

    def reset_weights_file(self, _=None) -> None:
        """docstring"""
        self.model.reset_weights()
        self.view.weights_filechooser.reset()
        self.view.weights_reset_button.disabled = True

    def _build_experiment_selector_options(self) -> list[tuple]:
        """Returns a (option_string, battery_id) list."""
        return [(self._cast_row_as_option(row), row["id"])
                for _, row in self.model.experiments.iterrows()]

    def _cast_row_as_option(self, row: dict) -> str:
        """docstring"""
        pk = row["id"]
        flag = self.model.get_experiment_extras(pk, "flag") or "❓"
        label = row["label"] or "Experiment"
        timestamp = row["ctime"]
        option = f" {flag} {pk} : {label} : {timestamp}"
        return option + f" : {status}" \
            if (status := self.model.get_experiment_extras(pk, "status")) \
            else option

    def _has_valid_selection(self) -> bool:
        """docstring"""

        plot_label = self.view.plot_type_selector.label
        experiment_ids = self.view.experiment_selector.value

        labels = [label for label, _ in self.view.STATISTICAL_PLOT_TYPES]

        if plot_label in labels and len(experiment_ids) < 2:
            self.display_info_message("Please select more than one experiment")
            return False

        return True
