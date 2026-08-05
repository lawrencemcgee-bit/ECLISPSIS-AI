import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: settingsPanel
    width: parent ? parent.width * 0.35 : 320
    height: parent ? parent.height * 0.5 : 240

    Rectangle {
        anchors.fill: parent
        color: "#181820"
        radius: 10

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            Label {
                text: "Settings"
                color: "#f0f0ff"
                font.pixelSize: 16
            }

            // Theme toggle
            RowLayout {
                spacing: 10
                Label { text: "Theme"; color: "#f0f0ff" }
                ComboBox {
                    id: themeDropdown
                    model: ["dark", "light"]
                    currentIndex: assistant.settings.theme === "dark" ? 0 : 1
                    onCurrentTextChanged: {
                        assistant.settings.theme = currentText
                        assistant.save_settings()
                        themeLoader.item.darkMode = (currentText === "dark")
                        root.color = themeLoader.item.background
                    }
                }
            }

            // Default agent
            RowLayout {
                spacing: 10
                Label { text: "Default Agent"; color: "#f0f0ff" }
                ComboBox {
                    id: agentDropdown
                    model: ["onenote", "weather", "news"]
                    currentIndex: model.indexOf(assistant.settings.last_agent)
                    onCurrentTextChanged: {
                        assistant.settings.last_agent = currentText
                        assistant.save_settings()
                        StateBridge.selectAgent(currentText)
                    }
                }
            }

            // Microphone toggle
            RowLayout {
                spacing: 10
                Label { text: "Microphone"; color: "#f0f0ff" }
                Switch {
                    id: micSwitch
                    checked: assistant.settings.mic_enabled
                    onToggled: {
                        assistant.settings.mic_enabled = checked
                        assistant.save_settings()
                        if (checked) StateBridge.toggleMic()
                        else StateBridge.toggleMic()
                    }
                }
            }

            Button {
                text: "Save Settings"
                Layout.alignment: Qt.AlignRight
                onClicked: assistant.save_settings()
            }
        }
    }
}
