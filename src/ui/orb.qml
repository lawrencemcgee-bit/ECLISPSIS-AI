import QtQuick

Rectangle {
    id: orb
    width: 160
    height: 160
    radius: width / 2

    property string assistantState: "idle"

    property color idleColor: "#3030ff"
    property color listeningColor: "#00cc88"
    property color thinkingColor: "#ffaa00"
    property color workingColor: "#ff3366"
    property color speakingColor: "#66aaff"
    property color errorColor: "#ff0000"

    color: {
        switch (assistantState) {
            case "listening": return listeningColor;
            case "thinking": return thinkingColor;
            case "working": return workingColor;
            case "speaking": return speakingColor;
            case "error": return errorColor;
            default: return idleColor;
        }
    }

    SequentialAnimation on scale {
        loops: Animation.Infinite

        NumberAnimation {
            from: assistantState === "thinking" ? 1.0 : 1.0
            to:   assistantState === "thinking" ? 1.25 : 1.1
            duration: assistantState === "thinking" ? 600 : 900
            easing.type: Easing.InOutQuad
        }

        NumberAnimation {
            from: assistantState === "thinking" ? 1.25 : 1.1
            to:   assistantState === "thinking" ? 1.0 : 1.0
            duration: assistantState === "thinking" ? 600 : 900
            easing.type: Easing.InOutQuad
        }
    }
}

