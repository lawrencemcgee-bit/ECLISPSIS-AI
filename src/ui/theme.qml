import QtQuick 2.15

QtObject {
    id: theme
    property bool darkMode: true

    property color background: darkMode ? "#101018" : "#f5f5ff"
    property color textPrimary: darkMode ? "#f0f0ff" : "#202030"

    function toggle() {
        darkMode = !darkMode
    }
}

