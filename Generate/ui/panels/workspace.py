from PyQt5.QtWidgets import QWidget, QVBoxLayout

from panels.load_curve import LoadCurvePanel
from panels.main_program import MainProgramPanel
from panels.requirement import RequirementPanel


class Design3RightPanel(QWidget):
    def __init__(self, project_json_getter=None, run_tuning_callback=None, parent=None):
        super().__init__(parent)
        self.controller_panel = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.main_program_panel = MainProgramPanel(
            project_json_getter=project_json_getter,
            structure_refresh_callback=self.refresh_structure,
        )
        self.load_curve_panel = LoadCurvePanel(project_json_getter=project_json_getter)
        self.requirement_panel = RequirementPanel(project_json_getter=project_json_getter)
        self.main_program_panel.set_workflow_widgets(
            load_curve_panel=self.load_curve_panel,
            requirement_panel=self.requirement_panel,
            run_tuning_callback=run_tuning_callback,
        )

        layout.addWidget(self.main_program_panel)

    def set_controller_panel(self, controller_panel):
        self.controller_panel = controller_panel

    def refresh_structure(self):
        if self.controller_panel is not None:
            self.controller_panel.refresh_from_project()

    def project_widgets(self):
        return [self.main_program_panel, self.load_curve_panel, self.requirement_panel]
