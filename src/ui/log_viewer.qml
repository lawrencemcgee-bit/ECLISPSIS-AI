import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: logViewer
    width: parent ? parent.width * 0.35 : 320
    height: parent ? parent.height * 0.5 : 240

    property string logText: ""

    Rectangle {
        anchors.fill: parent
        color: "#181820"
        radius: 10

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 6

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Label {
                    text: "Logs"
                    color: "#f0f0ff"
                    font.pixelSize: 14
                }

                Button {
                    text: "Refresh"
                    onClicked: logViewer.refresh()
                }
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true

                TextArea {
                    text: logViewer.logText
                    readOnly: true
                    color: "#f0f0ff"
                    font.pixelSize: 12
                    wrapMode: TextArea.NoWrap
                }
            }
        }
    }

    function refresh() {
        // simple file read via JS
        var path = Qt.resolvedUrl("../../logs/app.log")
        var xhr = new XMLHttpRequest()
        xhr.open("GET", path)
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
                logViewer.logText = xhr.responseText
            }
        }
        xhr.send()
    }
}
