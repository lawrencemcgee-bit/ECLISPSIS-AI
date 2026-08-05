import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15

Window {
    id: popup
    width: 480
    height: 360
    visible: true
    color: "#181820"
    title: windowTitle

    property string windowTitle: "Popup"
    property url contentSource: ""

    Loader {
        id: contentLoader
        anchors.fill: parent
        source: popup.contentSource
    }
}
