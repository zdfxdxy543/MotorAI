FONT_FAMILY = 'Segoe UI, Microsoft YaHei, Arial'

COLOR_PRIMARY = '#0f62fe'
COLOR_PRIMARY_HOVER = '#0a55df'
COLOR_PRIMARY_PRESSED = '#0848c7'
COLOR_PRIMARY_SOFT = '#eff6ff'
COLOR_PRIMARY_BORDER = '#bfdbfe'
COLOR_PRIMARY_TEXT = '#175cd3'

COLOR_TEXT = '#1f2937'
COLOR_TEXT_STRONG = '#0f172a'
COLOR_MUTED = '#64748b'
COLOR_SUBTLE = '#475569'
COLOR_BORDER = '#d9e2ec'
COLOR_BORDER_STRONG = '#cfd8e3'
COLOR_SURFACE = '#ffffff'
COLOR_BACKGROUND = '#eef2f7'
COLOR_PANEL = '#f8fafc'
COLOR_PANEL_HOVER = '#eef4ff'
COLOR_SELECTION = '#dbeafe'

COLOR_SUCCESS_BG = '#ecfdf3'
COLOR_SUCCESS_BORDER = '#abefc6'
COLOR_SUCCESS_TEXT = '#067647'
COLOR_ERROR_BG = '#fef3f2'
COLOR_ERROR_BORDER = '#fecdca'
COLOR_ERROR_TEXT = '#b42318'

RADIUS_CARD = 10
RADIUS_CONTROL = 8
RADIUS_BUBBLE = 10
RADIUS_SMALL = 6


def transparent_qss() -> str:
    return 'border:none;background:transparent;margin:0;padding:0;'


def surface_card_qss(object_name: str, radius: int = RADIUS_CARD) -> str:
    return (
        f'QFrame#{object_name}{{background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};'
        f'border-radius:{radius}px;}}'
        f'QFrame#{object_name} QLabel{{border:none;background:transparent;}}'
    )


def primary_button_qss(
    radius: int = RADIUS_CONTROL,
    padding: str = '7px 14px',
    include_disabled: bool = True,
) -> str:
    qss = (
        f'QPushButton{{background:{COLOR_PRIMARY};color:{COLOR_SURFACE};border:none;'
        f'border-radius:{radius}px;font-weight:600;padding:{padding};}}'
        f'QPushButton:hover{{background:{COLOR_PRIMARY_HOVER};}}'
        f'QPushButton:pressed{{background:{COLOR_PRIMARY_PRESSED};}}'
    )
    if include_disabled:
        qss += 'QPushButton:disabled{background:#9abafc;color:#f8fbff;}'
    return qss


def secondary_button_qss(radius: int = RADIUS_CONTROL, padding: str = '7px 14px') -> str:
    return (
        f'QPushButton{{background:{COLOR_PANEL};color:#344054;border:1px solid #d6deea;'
        f'border-radius:{radius}px;font-weight:600;padding:{padding};}}'
        f'QPushButton:hover{{background:{COLOR_PANEL_HOVER};border-color:#9fb7ff;}}'
        'QPushButton:disabled{color:#94a3b8;}'
    )


def ghost_button_qss(radius: int = RADIUS_CONTROL, padding: str = '7px 14px') -> str:
    return (
        f'QPushButton{{background:{COLOR_SURFACE};color:{COLOR_MUTED};border:1px solid #e2e8f0;'
        f'border-radius:{radius}px;font-weight:600;padding:{padding};}}'
        f'QPushButton:hover{{background:{COLOR_PANEL};}}'
        'QPushButton:disabled{color:#94a3b8;}'
    )


def flat_button_qss(radius: int = RADIUS_CONTROL, padding: str = '12px 24px') -> str:
    return (
        f'QPushButton{{background:#f3f4f6;border:none;outline:none;border-radius:{radius}px;'
        f'padding:{padding};font-size:12pt;color:#374151;}}'
        'QPushButton:hover{background:#e5e7eb;}'
        'QPushButton:pressed{background:#d1d5db;}'
        'QPushButton:focus{outline:none;}'
    )


def status_label_qss() -> str:
    return (
        f'QLabel#taskStatusLabel{{background:{COLOR_PANEL};border:none;'
        f'border-radius:{RADIUS_CARD}px;padding:8px 10px;color:{COLOR_SUBTLE};}}'
    )


def app_qss() -> str:
    return f"""
            QMainWindow {{
                background: {COLOR_BACKGROUND};
            }}
            QWidget {{
                color: {COLOR_TEXT};
                font-family: {FONT_FAMILY};
                font-size: 10pt;
            }}
            QLabel {{
                color: {COLOR_TEXT};
            }}
            QWidget#chatStreamWidget,
            QWidget#chatStreamContainer,
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
                border: none;
            }}
            QFrame#ControllerStructureCanvas,
            QFrame#CurveCanvas,
            QTextEdit,
            QTableWidget,
            QTabWidget::pane,
            QMenu,
            QDialog,
            QWidget#panelCard {{
                background: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: {RADIUS_CARD}px;
            }}
            QLabel#chatBubbleTitle {{
                font-size: 10pt;
                font-weight: 600;
                color: {COLOR_MUTED};
            }}
            QLabel#chatBubbleBody {{
                font-size: 11pt;
                line-height: 1.55;
            }}
            QTabWidget::pane {{
                padding: 6px;
            }}
            QTabBar::tab {{
                background: #e9eef5;
                color: #344054;
                border: 1px solid {COLOR_BORDER_STRONG};
                border-bottom: none;
                border-top-left-radius: {RADIUS_CONTROL}px;
                border-top-right-radius: {RADIUS_CONTROL}px;
                min-width: 120px;
                padding: 8px 14px;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                background: {COLOR_SURFACE};
                color: {COLOR_PRIMARY};
                font-weight: 600;
            }}
            QTabBar::tab:hover {{
                background: #f6f8fc;
            }}
            QPushButton {{
                background: {COLOR_SURFACE};
                color: {COLOR_TEXT_STRONG};
                border: 1px solid {COLOR_BORDER_STRONG};
                border-radius: {RADIUS_CONTROL}px;
                padding: 7px 14px;
                min-height: 18px;
            }}
            QPushButton:hover {{
                background: #f3f7ff;
                border-color: #7da7ff;
            }}
            QPushButton:pressed {{
                background: #dce8ff;
            }}
            QPushButton#primaryButton {{
                background: {COLOR_PRIMARY};
                color: white;
                border: none;
                font-weight: 600;
            }}
            QPushButton#primaryButton:hover {{
                background: {COLOR_PRIMARY_HOVER};
            }}
            QPushButton#ghostButton,
            QPushButton#secondaryActionButton {{
                background: {COLOR_PANEL};
                color: #344054;
                border: 1px solid #d6deea;
                font-weight: 600;
            }}
            QPushButton#secondaryActionButton {{
                min-width: 112px;
            }}
            QPushButton#ghostButton:hover,
            QPushButton#secondaryActionButton:hover {{
                background: {COLOR_PANEL_HOVER};
                border-color: #9fb7ff;
            }}
            QToolButton {{
                background: {COLOR_SURFACE};
                color: {COLOR_TEXT_STRONG};
                border: 1px solid {COLOR_BORDER_STRONG};
                border-radius: {RADIUS_CONTROL}px;
                padding: 7px 14px;
            }}
            QToolButton:hover {{
                background: #f3f7ff;
                border-color: #7da7ff;
            }}
            QTextEdit {{
                padding: 10px;
                selection-background-color: {COLOR_SELECTION};
                line-height: 1.4;
            }}
            QTableWidget {{
                gridline-color: #e1e8f0;
                selection-background-color: {COLOR_SELECTION};
                selection-color: #111827;
            }}
            QHeaderView::section {{
                background: #f2f6fb;
                color: #344054;
                border: none;
                border-bottom: 1px solid {COLOR_BORDER};
                padding: 8px 10px;
                font-weight: 600;
            }}
            QMenu {{
                border: 1px solid {COLOR_BORDER};
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 24px 8px 18px;
                border-radius: {RADIUS_CONTROL}px;
                margin: 2px 0;
            }}
            QMenu::item:selected {{
                background: #eaf1ff;
                color: {COLOR_PRIMARY};
            }}
            QDialog {{
                background: #f7f9fc;
            }}
            """
