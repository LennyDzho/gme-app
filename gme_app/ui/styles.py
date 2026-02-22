"""Application stylesheet."""

APP_STYLE = """
QMainWindow, QWidget {
    background: #eef2ff;
    color: #1f2746;
    font-family: "Segoe UI";
    font-size: 14px;
}

QLineEdit, QTextEdit {
    border: 1px solid #d7def3;
    border-radius: 12px;
    padding: 10px 12px;
    background: #ffffff;
    selection-background-color: #5d8bff;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #6a8eff;
}

QPushButton {
    border: none;
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: 600;
}

QPushButton:disabled {
    background: #d8def2;
    color: #8991b1;
}

QPushButton#PrimaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4e7fff, stop:1 #72a1ff);
    color: #ffffff;
}

QPushButton#PrimaryButton:hover:!disabled {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3f72f6, stop:1 #5e94ff);
}

QPushButton#SecondaryButton {
    background: #edf2ff;
    color: #2d4c9f;
    border: 1px solid #d0daf8;
}

QPushButton#SecondaryButton:hover:!disabled {
    background: #e2eaff;
}

QFrame#AuthCard {
    background: #f8faff;
    border: 1px solid #dfe5f7;
    border-radius: 26px;
}

QFrame#AuthHeader {
    background: #eef3ff;
    border: 1px solid #dbe4fb;
    border-radius: 14px;
}

QLabel#AuthLogo {
    font-size: 34px;
    font-weight: 700;
    color: #2f4376;
    background: transparent;
}

QLabel#AuthHeadline {
    font-size: 32px;
    font-weight: 700;
    color: #1f2746;
}

QLabel#AuthSubhead {
    font-size: 15px;
    color: #56608a;
    background: transparent;
}

QTabWidget#AuthTabs::pane {
    border: 1px solid #dbe2f7;
    border-radius: 14px;
    background: #f3f7ff;
    margin-top: 0px;
}

QTabBar::tab {
    min-width: 0;
    padding: 10px 14px;
    margin: 2px;
    border-radius: 10px;
    color: #66709a;
    background: transparent;
    font-size: 16px;
}

QTabBar::tab:selected {
    color: #1f2a52;
    font-weight: 700;
    background: #e8efff;
}

QLabel#InfoLabel {
    color: #4d5885;
    font-size: 13px;
}

QFrame#AuthInfoPanel {
    background: #eef3ff;
    border: 1px solid #dbe5fb;
    border-radius: 16px;
}

QLabel#AuthInfoTitle {
    color: #253666;
    font-size: 18px;
    font-weight: 700;
    background: transparent;
}

QLabel#AuthInfoText {
    color: #55638e;
    font-size: 14px;
    background: transparent;
}

QLabel#ErrorLabel {
    color: #c63f57;
    font-size: 13px;
}

QFrame#Sidebar {
    background: #f6f8ff;
    border: 1px solid #dfe4f8;
    border-radius: 18px;
}

QPushButton#SidebarNavButton {
    text-align: left;
    border-radius: 10px;
    background: transparent;
    color: #495581;
    padding: 9px 12px;
}

QPushButton#SidebarNavButton:hover {
    background: #eaf0ff;
}

QPushButton#SidebarNavButton[active="true"] {
    background: #dce8ff;
    color: #2a4180;
}

QFrame#MainPanel {
    background: #ffffff;
    border: 1px solid #dde4f9;
    border-radius: 18px;
}

QFrame#HeaderBar {
    background: #f8faff;
    border: 1px solid #e2e7f9;
    border-radius: 14px;
}

QLabel#GreetingLabel {
    font-size: 28px;
    font-weight: 700;
    color: #1c2649;
}

QFrame#MetricCard {
    background: #f8faff;
    border: 1px solid #dce4fb;
    border-radius: 14px;
}

QLabel#MetricTitle {
    color: #61709d;
    font-size: 13px;
}

QLabel#MetricValue {
    color: #1e2950;
    font-size: 24px;
    font-weight: 700;
}

QFrame#ProjectCard {
    background: #fbfcff;
    border: 1px solid #dde5fb;
    border-radius: 16px;
}

QFrame#ProjectCard:hover {
    border: 1px solid #c7d6ff;
}

QLabel#ProjectTitle {
    font-size: 18px;
    font-weight: 700;
    color: #203059;
}

QLabel#ProjectMeta {
    color: #5a668f;
    font-size: 13px;
}

QLabel#StatusBadge {
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 700;
}

QLabel#StatusBadge[status="draft"] {
    background: #e8eefc;
    color: #345aa3;
}

QLabel#StatusBadge[status="in_progress"] {
    background: #fff4d8;
    color: #8e6500;
}

QLabel#StatusBadge[status="done"] {
    background: #dff5e8;
    color: #1e7a4b;
}

QLabel#StatusBadge[status="archived"] {
    background: #eceff7;
    color: #5d6788;
}

QLabel#StatusBadge[status="scheduled"] {
    background: #e8eefc;
    color: #345aa3;
}

QLabel#StatusBadge[status="pending"] {
    background: #f6f0ff;
    color: #6b4cb0;
}

QLabel#StatusBadge[status="running"] {
    background: #fff4d8;
    color: #8e6500;
}

QLabel#StatusBadge[status="completed"] {
    background: #dff5e8;
    color: #1e7a4b;
}

QLabel#StatusBadge[status="failed"] {
    background: #fde8ea;
    color: #b6374b;
}

QLabel#StatusBadge[status="cancelled"] {
    background: #eceff7;
    color: #5d6788;
}

QFrame#EmptyState {
    border-radius: 16px;
    border: 1px dashed #cad6f8;
    background: #f9fbff;
}

QLabel#SectionTitle {
    font-size: 24px;
    font-weight: 700;
    color: #1f2a52;
}

QLabel#SectionHint {
    color: #65719c;
}

QTableWidget#RunsTable {
    border: 1px solid #dce4fb;
    border-radius: 12px;
    background: #ffffff;
    gridline-color: #eef2fe;
}

QHeaderView::section {
    background: #f3f7ff;
    color: #445280;
    border: none;
    border-bottom: 1px solid #dce4fb;
    padding: 8px 10px;
    font-weight: 600;
}

QTableWidget::item {
    border-bottom: 1px solid #eef2fe;
    padding: 8px;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: #c8d3f2;
    border-radius: 5px;
    min-height: 30px;
}
"""
