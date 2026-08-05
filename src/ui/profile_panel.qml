import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: profilePanel
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
                text: "Profile"
                color: "#f0f0ff"
                font.pixelSize: 16
            }

            RowLayout {
                spacing: 10
                Label { text: "Name"; color: "#f0f0ff" }
                TextField {
                    id: nameField
                    text: assistant.profile.name
                    onTextChanged: StateBridge.updateUserName(text)
                }
            }

            RowLayout {
                spacing: 10
                Label { text: "Avatar"; color: "#f0f0ff" }
                ComboBox {
                    id: avatarDropdown
                    model: ["default.png", "avatar1.png", "avatar2.png"]
                    currentIndex: model.indexOf(assistant.profile.avatar)
                    onCurrentTextChanged: StateBridge.updateAvatar(currentText)
                }
            }

            RowLayout {
                spacing: 10
                Label { text: "Typing Indicator"; color: "#f0f0ff" }
                Switch {
                    id: typingSwitch
                    checked: assistant.profile.preferences.show_typing_indicator
                    onToggled: StateBridge.updateTypingPreference(checked)
                }
            }

            RowLayout {
                spacing: 10
                Label { text: "Sound Effects"; color: "#f0f0ff" }
                Switch {
                    id: soundSwitch
                    checked: assistant.profile.preferences.enable_sound_effects
                    onToggled: {
                        StateBridge.updateSoundPreference(checked)
                        soundLoader.item.enabled = checked
                    }
                }
            }

            Button {
                text: "Save Profile"
                Layout.alignment: Qt.AlignRight
                onClicked: assistant.save_profile()
            }
        }
    }
}
