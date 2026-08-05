import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: toast
    width: parent ? parent.width : 400
    height: 60
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: 40
    opacity: 0.0
    visible: false

    property string message: ""
    property int duration: 2200

    Rectangle {
        anchors.centerIn: parent
        width: message.length * 8 + 60
        height: 40
        radius: 10
        color: "#303040"
        border.color: "#606080"
        border.width: 1

        Text {
            anchors.centerIn: parent
            text: toast.message
            color: "white"
            font.pixelSize: 14
        }
    }

    SequentialAnimation {
        id: anim
        PropertyAnimation { target: toast; property: "opacity"; to: 1.0; duration: 250 }
        PauseAnimation { duration: toast.duration }
        PropertyAnimation { target: toast; property: "opacity"; to: 0.0; duration: 300 }
        ScriptAction { script: toast.visible = false }
    }

    function show(msg) {
        toast.message = msg
        toast.visible = true
        anim.start()
    }
}
