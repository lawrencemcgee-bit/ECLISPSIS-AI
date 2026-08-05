import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: quickPanel
    width: parent ? parent.width * 0.4 : 400
    height: parent ? parent.height * 0.4 : 260

    Rectangle {
        anchors.fill: parent
        color: "#181820"
        radius: 10

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            Label {
                text: "Quick Actions"
                color: "#f0f0ff"
                font.pixelSize: 16
            }

            Button {
                text: "Toggle Mic (Ctrl+Shift+M)"
                onClicked: StateBridge.toggleMic()
            }

            Button {
                text: "Open Logs (Ctrl+Shift+L)"
                onClicked: logViewerLoader.visible = !logViewerLoader.visible
            }

            Button {
                text: "Open Profile (Ctrl+Shift+P)"
                onClicked: profileLoader.visible = !profileLoader.visible
            }

            Button {
                text: "Run Selected Agent"
                onClicked: StateBridge.runSelectedAgent()
            }
        }
    }
}
