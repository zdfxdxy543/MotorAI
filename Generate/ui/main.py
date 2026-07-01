from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from ui_main import MainWindow
import os


def main():
    app = QApplication([])
    
    icon_path = os.path.join(os.path.dirname(__file__), '..', 'icon.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    win = MainWindow()
    win.show()
    app.exec_()


if __name__ == '__main__':
    main()
