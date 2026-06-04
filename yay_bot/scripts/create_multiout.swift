// 複数出力装置（stacked aggregate）を CoreAudio API で作成する。
// 用途: Spotify 等のシステム音を BlackHole（bot 取り込み用）と実スピーカーの両方へ同時出力。
//   master = Steinberg（ハードクロック親）、drift 補正 = BlackHole 側。
// 使い方: swift create_multiout.swift            … 作成
//         swift create_multiout.swift --list     … デバイス一覧（UID付き）
//         swift create_multiout.swift --remove   … 「Yay出力」を削除
import CoreAudio
import Foundation

let DEVICE_NAME = "Yay出力"
let DEVICE_UID  = "com.emocute.yayout"
let MASTER_MATCH = "Steinberg UR22mkII"   // 実出力（究の耳・クロック親）
let DRIFT_MATCH  = "BlackHole 2ch"        // bot 取り込み・drift 補正側

func cfStr<T>(_ obj: AudioObjectID, _ selector: AudioObjectPropertySelector) -> T? {
  var addr = AudioObjectPropertyAddress(mSelector: selector,
    mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
  var size = UInt32(MemoryLayout<CFString?>.size)
  var val: CFString? = nil
  let st = withUnsafeMutablePointer(to: &val) {
    AudioObjectGetPropertyData(obj, &addr, 0, nil, &size, $0)
  }
  if st != noErr { return nil }
  return val as? T
}

func allDevices() -> [AudioObjectID] {
  var addr = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDevices,
    mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
  var size: UInt32 = 0
  AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size)
  let n = Int(size) / MemoryLayout<AudioObjectID>.size
  var ids = [AudioObjectID](repeating: 0, count: n)
  AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &ids)
  return ids
}

func hasOutput(_ dev: AudioObjectID) -> Bool {
  var addr = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyStreamConfiguration,
    mScope: kAudioObjectPropertyScopeOutput, mElement: kAudioObjectPropertyElementMain)
  var size: UInt32 = 0
  if AudioObjectGetPropertyDataSize(dev, &addr, 0, nil, &size) != noErr { return false }
  let ptr = UnsafeMutableRawPointer.allocate(byteCount: Int(size), alignment: 16)
  defer { ptr.deallocate() }
  if AudioObjectGetPropertyData(dev, &addr, 0, nil, &size, ptr) != noErr { return false }
  let abl = ptr.assumingMemoryBound(to: AudioBufferList.self)
  let buffers = UnsafeMutableAudioBufferListPointer(abl)
  for b in buffers where b.mNumberChannels > 0 { return true }
  return false
}

func info(_ dev: AudioObjectID) -> (name: String, uid: String)? {
  guard let name: String = cfStr(dev, kAudioObjectPropertyName),
        let uid: String = cfStr(dev, kAudioDevicePropertyDeviceUID) else { return nil }
  return (name, uid)
}

let args = CommandLine.arguments

if args.contains("--list") {
  for d in allDevices() {
    if let i = info(d) {
      print("\(hasOutput(d) ? "OUT" : "in ")  \(i.name)  ::  \(i.uid)")
    }
  }
  exit(0)
}

if args.contains("--remove") {
  for d in allDevices() {
    if let i = info(d), i.uid == DEVICE_UID || i.name == DEVICE_NAME {
      let st = AudioHardwareDestroyAggregateDevice(d)
      print(st == noErr ? "削除: \(i.name)" : "削除失敗 st=\(st)")
      exit(st == noErr ? 0 : 1)
    }
  }
  print("対象なし（既に無い）"); exit(0)
}

// --- 作成 ---
var masterUID: String? = nil
var driftUID: String? = nil
for d in allDevices() {
  guard hasOutput(d), let i = info(d) else { continue }
  if i.name.contains(MASTER_MATCH) { masterUID = i.uid }
  if i.name.contains(DRIFT_MATCH)  { driftUID  = i.uid }
}
guard let master = masterUID, let drift = driftUID else {
  print("デバイス未検出 master=\(masterUID ?? "nil") drift=\(driftUID ?? "nil")"); exit(1)
}

// 既存の同名/同UIDがあれば消してから作り直す（冪等）
for d in allDevices() {
  if let i = info(d), i.uid == DEVICE_UID || i.name == DEVICE_NAME {
    AudioHardwareDestroyAggregateDevice(d)
  }
}

let subList: [[String: Any]] = [
  // master を先頭に
  [kAudioSubDeviceUIDKey as String: master],
  [kAudioSubDeviceUIDKey as String: drift,
   kAudioSubDeviceDriftCompensationKey as String: 1],
]
let desc: [String: Any] = [
  kAudioAggregateDeviceNameKey as String: DEVICE_NAME,
  kAudioAggregateDeviceUIDKey as String: DEVICE_UID,
  kAudioAggregateDeviceSubDeviceListKey as String: subList,
  kAudioAggregateDeviceMasterSubDeviceKey as String: master,
  kAudioAggregateDeviceIsStackedKey as String: 1,   // 1 = 複数出力装置（stacked）
]

var newID: AudioObjectID = 0
let st = AudioHardwareCreateAggregateDevice(desc as CFDictionary, &newID)
if st != noErr { print("作成失敗 st=\(st)"); exit(1) }
print("作成OK: \(DEVICE_NAME) id=\(newID) master=\(master) drift=\(drift)")
