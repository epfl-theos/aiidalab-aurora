# -*- coding: utf-8 -*-

import pandas as pd
import ipywidgets as ipw
from IPython.display import display
from .sample import SampleFromId, SampleFromSpecs, SampleFromRecipe
from .cycling import CyclingStandard, CyclingCustom
from .tomato import TomatoSettings
from .analyze import PreviewResults
from ..schemas.battery import BatterySample, BatterySpecs
from ..schemas.utils import _remove_empties_from_dict

import aiida
from aiida import load_profile
load_profile()
from aiida.orm import load_node, load_code, load_computer, load_group
from aiida.engine import submit

BatterySampleData = aiida.plugins.DataFactory('aurora.batterysample')
CyclingSpecsData = aiida.plugins.DataFactory('aurora.cyclingspecs')
TomatoSettingsData = aiida.plugins.DataFactory('aurora.tomatosettings')
BatteryCyclerExperiment = aiida.plugins.CalculationFactory('aurora.cycler')

TomatoMonitorData = aiida.plugins.DataFactory('calcmonitor.monitor.tomatobiologic')
TomatoMonitorCalcjob = aiida.plugins.CalculationFactory('calcmonitor.calcjob_monitor')

def submit_experiment(sample, method, job_settings):
    
    sample_node = BatterySampleData(sample.dict())
    if job_settings.get('sample_node_label'):
        sample_node.label = job_settings.get('sample_node_label')
    sample_node.store()

    method_node = CyclingSpecsData(method.dict())
    if job_settings.get('method_node_label'):
        method_node.label = job_settings.get('method_node_label')
    method_node.store()
        
    code = load_code('ketchup@localhost')
    
    builder = BatteryCyclerExperiment.get_builder()
    builder.battery_sample = sample_node
    builder.code = code
    builder.technique = method_node
    # builder.metadata.dry_run = True
    ## TODO: set these 2 parameters
    # unlock_when_finished
    # verbosity
    
    process = submit(builder)
    process.label = job_settings.get('calc_node_label', '')
    print(f"Job <{process.pk}> submitted to AiiDA...")

    return process


class MainPanel(ipw.VBox):

    _ACCORDION_STEPS = ['Sample selection', 'Cycling Protocol', 'Job Settings', 'Submit Job', 'Visualize Results']
    _SAMPLE_INPUT_LABELS = ['Select from ID', 'Select from Specs', 'Make from Recipe']
    _SAMPLE_INPUT_METHODS = ['id', 'specs', 'recipe']
    _METHOD_LABELS = ['Standardized', 'Customized']
    w_header = ipw.HTML(value="<h2>Aurora</h2>")
    _SAMPLE_BOX_LAYOUT = {'width': '90%', 'border': 'solid blue 2px', 'align_content': 'center', 'margin': '5px', 'padding': '5px'}
    _BOX_LAYOUT = {'width': '100%'}
    _BOX_STYLE = {'description_width': '25%'}
    _BUTTON_STYLE = {'description_width': '30%'}
    _BUTTON_LAYOUT = {'margin': '5px'}

    #######################################################################################
    # FAKE TRAITLES
    # these are the properties shared between widgets
    # TODO: replace them with Traitlets defined for each widget, that are connected through `dlink` in this class
    # (see Quantum Espresso app for an example)
    #######################################################################################
    @property
    def selected_battery_sample(self):
        "The Battery Sample selected. Used by a BatteryCyclerExperiment."
        return self._selected_battery_sample
    
    @property
    def selected_battery_specs(self):
        "The Battery Specs selected. Used by an hypothetical BuildBatteryCalcJob."
        return self._selected_battery_specs

    @property
    def selected_recipe(self):
        "The Battery Recipe selected. Used by an hypothetical BuildBatteryCalcJob."
        return self._selected_battery_recipe

    @property
    def selected_cycling_protocol(self):
        "The Cycling Specs selected. Used by a BatteryCyclerExperiment."
        return self._selected_cycling_protocol

    @property
    def selected_tomato_settings(self):
        "The Tomato Settings selected. Used by a BatteryCyclerExperiment."
        return self._selected_tomato_settings

    @property
    def selected_monitor_job_settings(self):
        "The Tomato Monitor Settings selected. Used by a TomatoMonitorCalcjob."
        return self._selected_monitor_job_settings

    #######################################################################################
    # SAMPLE SELECTION
    #######################################################################################
    def return_selected_sample(self, sample_widget_obj):
        "Store the selected sample in `self.selected_battery_sample` and call post action."
        self._selected_battery_sample = BatterySample.parse_obj(_remove_empties_from_dict(sample_widget_obj.selected_sample_dict))
        self.post_sample_selection()

    def return_selected_specs_recipe(self, sample_widget_obj):
        "Store the selected specs & recipe in `self.selected_battery_specs` & `self.selected_recipe` and call post action (TODO)."
        self._selected_battery_specs = BatterySpecs.parse_obj(_remove_empties_from_dict(sample_widget_obj.selected_specs_dict))
        self._selected_recipe = sample_widget_obj.selected_recipe_dict
        # TODO: call post action

    def switch_to_recipe(self, specs_widget_obj):
        "Switch Sample tab to sample-from-recipe, copying over the selected specs"
        self.w_sample_selection_tab.selected_index = 2
        self.w_sample_from_recipe.w_specs_manufacturer.value = specs_widget_obj.w_specs_manufacturer.value
        self.w_sample_from_recipe.w_specs_composition.value = specs_widget_obj.w_specs_composition.value
        self.w_sample_from_recipe.w_specs_form_factor.value = specs_widget_obj.w_specs_form_factor.value
        self.w_sample_from_recipe.w_specs_capacity.value = specs_widget_obj.w_specs_capacity.value

    def display_tested_sample_preview(self):
        "Display sample properties in the Method tab."
        self.w_test_sample_preview.clear_output()
        if self.selected_battery_sample is not None:
            with self.w_test_sample_preview:
                # display(query_available_samples(write_pd_query_from_dict({'battery_id': self.w_select_sample_id.value})))
                display(pd.json_normalize(self.selected_battery_sample.dict()).iloc[0])

    def post_sample_selection(self):
        "Switch to method accordion tab"
        self.w_main_accordion.selected_index = 1
        self.display_tested_sample_preview()

    @property
    def sample_selection_method(self):
        if self.w_sample_selection_tab.selected_index is not None:
            return self._SAMPLE_INPUT_METHODS[self.w_sample_selection_tab.selected_index]

    #######################################################################################
    # METHOD SELECTION
    #######################################################################################
    def return_selected_protocol(self, cycling_widget_obj):
        self._selected_cycling_protocol = cycling_widget_obj.protocol_steps_list
        self.post_protocol_selection()

    def post_protocol_selection(self):
        "Switch to Tomato settings accordion tab."
        if self.selected_battery_sample is None:
            raise ValueError("A Battery sample was not selected!")
        # self.w_settings_tab.set_default_calcjob_node_label(self.selected_battery_sample_node.label, self.selected_cycling_protocol_node.label)  # TODO: uncomment this
        self.w_main_accordion.selected_index = 2

    #######################################################################################
    # TOMATO SETTINGS SELECTION
    #######################################################################################
    def return_selected_settings(self, settings_widget_obj):
        self._selected_tomato_settings = settings_widget_obj.selected_tomato_settings
        self._selected_monitor_job_settings = settings_widget_obj.selected_monitor_job_settings
        self.post_settings_selection()

    def post_settings_selection(self):
        "Switch to jobs submission accordion tab."
        self.w_main_accordion.selected_index = 3

    #######################################################################################
    # SUBMIT JOB
    #######################################################################################
    def display_job_input_preview(self, status, err_msg=""):
        "Display the selected job inputs, whether the job can be submitted (status) and the reason (err_msg)."
        # TODO: add preview of job inputs!
        self.w_job_preview.clear_output()
        with self.w_job_preview:
            if status:
                print(f"✅ {err_msg}")
            else:
                print(f"❌ {err_msg}")

    def presubmission_checks(self, dummy=None):
        "Verify that all the input is there. If so, enable submission button."
        if self.w_main_accordion.selected_index == 3:
            try:
                if self.selected_battery_sample is None:
                    raise ValueError("A Battery sample was not selected!")
                if self.selected_cycling_protocol is None:
                    raise ValueError("A Cycling protocol was not selected!")
                if self.selected_tomato_settings is None or self.selected_monitor_job_settings is None:
                    raise ValueError("Tomato settings were not selected!")

                print(f"Battery Sample:\n  {self.selected_battery_sample}")
                print(f"Cycling Protocol:\n  {self.selected_cycling_protocol}")
                print(f"Tomato Settings:\n  {self.selected_tomato_settings}")
                print(f"Monitor Job Settings:\n  {self.selected_monitor_job_settings}")
            except ValueError as err:
                self.w_submit_button.disabled = True
                self.display_job_input_preview(False, err)
            else:
                self.w_submit_button.disabled = False
                self.display_job_input_preview(True, "All good!")
    
    def submit_job(self):
        self.process = submit_experiment(
            sample=self.selected_battery_sample,
            method=self.selected_cycling_protocol,
            tomato_settings=self.selected_tomato_settings,
            monitor_settings=self.selected_monitor_job_settings,
        )
        print(f"Job <{self.process.pk}> submitted to AiiDA...")

        self.w_main_accordion.selected_index = 4

    #######################################################################################
    # RESET
    #######################################################################################

    def reset_sample_selection(self, dummy=None):
        "Reset sample data."
        self._selected_battery_sample = None
        self._selected_battery_specs = None
        self._selected_recipe = None

    def reset_all_inputs(self, dummy=None):
        "Reset all the selected inputs."
        self._selected_battery_sample = None
        self._selected_battery_specs = None
        self._selected_recipe = None
        self._selected_cycling_protocol = None
        self._selected_tomato_settings = None
        self._selected_monitor_job_settings = None

    def reset(self, dummy=None):
        "Reset the interface."
        # TODO: properly reinitialize each widget
        self.reset_all_inputs()
        self.w_main_accordion.selected_index = 0

    #######################################################################################
    # MAIN
    #######################################################################################
    def __init__(self):
        
        # initialize variables
        self.reset_all_inputs()

        # Sample selection
        self.w_sample_from_id = SampleFromId(validate_callback_f=self.return_selected_sample)
        self.w_sample_from_specs = SampleFromSpecs(validate_callback_f=self.return_selected_sample, recipe_callback_f=self.switch_to_recipe)
        self.w_sample_from_recipe = SampleFromRecipe(validate_callback_f=self.return_selected_specs_recipe)

        self.w_sample_selection_tab = ipw.Tab(
            children=[self.w_sample_from_id, self.w_sample_from_specs, self.w_sample_from_recipe],
            selected_index=0)
        for i, title in enumerate(self._SAMPLE_INPUT_LABELS):
            self.w_sample_selection_tab.set_title(i, title)

        # Method selection
        self.w_test_sample_label = ipw.HTML("Selected sample:")
        self.w_test_sample_preview = ipw.Output(layout=self._SAMPLE_BOX_LAYOUT)
        self.w_test_standard = CyclingStandard(lambda x: x)
        self.w_test_custom = CyclingCustom(validate_callback_f=self.return_selected_protocol)
        self.w_test_method_tab = ipw.Tab(
            children=[self.w_test_standard, self.w_test_custom],
            selected_index=1)
        for i, title in enumerate(self._METHOD_LABELS):
            self.w_test_method_tab.set_title(i, title)

        self.w_test_tab = ipw.VBox([
            self.w_test_sample_label,
            self.w_test_sample_preview,
            self.w_test_method_tab,
        ])

        # Settings selection
        self.w_settings_tab = TomatoSettings(validate_callback_f=self.return_selected_settings)

        # Submit
        self.w_job_preview = ipw.Output()  # TODO: write preview of the job inputs
        self.w_submit_button = ipw.Button(
            description="SUBMIT",
            button_style="success", tooltip="Submit the experiment", icon="play",
            disabled=True,
            style=self._BUTTON_STYLE, layout=self._BUTTON_LAYOUT)

        self.w_submit_tab = ipw.VBox([
            self.w_job_preview,
            self.w_submit_button
        ])

        # Results
        self.w_results_tab = PreviewResults()

        # Reset
        self.w_reset_button = ipw.Button(
            description="RESET",
            button_style="danger", tooltip="Start over", icon="times",
            style=self._BUTTON_STYLE, layout=self._BUTTON_LAYOUT)

        ########################################################################
        # MAIN ACCORDION
        self.w_main_accordion = ipw.Accordion(children=[
            self.w_sample_selection_tab,
            self.w_test_tab,
            self.w_settings_tab,
            self.w_submit_tab,
            self.w_results_tab
        ])
        for i, title in enumerate(self._ACCORDION_STEPS):
            self.w_main_accordion.set_title(i, title)

        super().__init__()
        self.children = [
            self.w_header,
            self.w_main_accordion,
            self.w_reset_button,
        ]

        # setup automations
        ## reset selected sample/specs/recipe when the user selects another sample input tab
        self.w_sample_selection_tab.observe(self.reset_sample_selection, names='selected_index')
        ## trigger presubmission checks when we are in the "Submit Job" accordion tab
        self.w_main_accordion.observe(self.presubmission_checks, names='selected_index')

        self.w_submit_button.on_click(self.submit_job)
        self.w_reset_button.on_click(self.reset)
