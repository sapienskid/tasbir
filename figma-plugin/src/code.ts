// Figma Main Thread — has access to figma.* API and the document scene graph.

import type { UiMessage } from './messages'

function base64ToBytes(base64: string): Uint8Array {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
  let clean = base64.replace(/[^A-Za-z0-9+/=]/g, '')
  const padding = clean.endsWith('==') ? 2 : clean.endsWith('=') ? 1 : 0
  clean = clean.replace(/=+$/, '')
  const len = (clean.length * 3) / 4 - padding
  const bytes = new Uint8Array(len)
  let pos = 0
  for (let i = 0; i < clean.length; i += 4) {
    const enc1 = chars.indexOf(clean[i])
    const enc2 = chars.indexOf(clean[i + 1])
    const enc3 = chars.indexOf(clean[i + 2] || 'A')
    const enc4 = chars.indexOf(clean[i + 3] || 'A')
    bytes[pos++] = (enc1 << 2) | (enc2 >> 4)
    if (pos < len) bytes[pos++] = ((enc2 & 15) << 4) | (enc3 >> 2)
    if (pos < len) bytes[pos++] = ((enc3 & 3) << 6) | enc4
  }
  return bytes
}

let apiBaseUrl = 'http://localhost:8787'
let apiKey = ''

figma.showUI(__html__, { width: 400, height: 600, themeColors: true })

async function loadSettings() {
  try {
    const url = await figma.clientStorage.getAsync('tasbir-api-base-url')
    if (url) apiBaseUrl = url
    const key = await figma.clientStorage.getAsync('tasbir-api-key')
    if (key) apiKey = key
  } catch {}
}

function postToUi(msg: UiMessage) {
  figma.ui.postMessage(msg)
}

figma.ui.onmessage = async (msg: any) => {
  switch (msg.type) {
    case 'SETTINGS_LOADED': {
      break
    }
    case 'CLOSE': {
      figma.ui.close()
      break
    }
    case 'NOTIFY': {
      figma.notify(msg.message, { timeout: msg.timeout || 3000 })
      break
    }
    case 'CREATE_FRAMES_FROM_ASSETS': {
      const assets = msg.payload.assets as Record<string, { url: string; format: string }>
      const metadata = msg.payload.metadata as Record<string, { width: number; height: number; slug: string; html: string; template_html?: string; slot_values?: Record<string, string> }>
      const formats = msg.payload.formats as string[]

      if (!assets || !formats) break

      // Group frames into a section
      const frames: FrameNode[] = []
      for (const format of formats) {
        const asset = assets[format]
        const meta = metadata?.[format]
        if (!asset || !asset.url) continue

        const base64Match = asset.url.match(/^data:image\/png;base64,(.+)$/)
        if (!base64Match) continue

        const bytes = base64ToBytes(base64Match[1])

        const image = figma.createImage(bytes)
        const frame = figma.createFrame()
        const w = meta?.width || 1080
        const h = meta?.height || 1080
        frame.resize(w, h)
        frame.name = `${format} - ${meta?.slug || 'generated'}`
        frame.fills = [{ type: 'IMAGE', imageHash: image.hash, scaleMode: 'FILL' }]
        frame.clipsContent = true

        // Store metadata on the frame for later editing
        const frameMeta: Record<string, any> = { format, slug: meta?.slug || '', width: w, height: h }
        if (meta?.html) frameMeta.html = meta.html
        if (meta?.template_html) frameMeta.template_html = meta.template_html
        if (meta?.slot_values) frameMeta.slot_values = meta.slot_values
        frame.setPluginData('tasbir', JSON.stringify(frameMeta))

        figma.currentPage.appendChild(frame)
        frames.push(frame)
      }

      // Layout frames in a grid
      if (frames.length > 0) {
        const gap = 80
        const cols = Math.min(frames.length, 3)
        for (let i = 0; i < frames.length; i++) {
          const col = i % cols
          const row = Math.floor(i / cols)
          frames[i].x = col * (frames[i].width + gap)
          frames[i].y = row * (frames[i].height + gap)
        }
        figma.viewport.scrollAndZoomIntoView(frames)
        figma.notify(`Created ${frames.length} social post frame(s)`)
        postToUi({ type: 'FRAME_CREATED', frameId: frames[0]?.id })
      }
      break
    }
    case 'UPDATE_FRAME_FILL': {
      const { frameId, dataUri } = msg.payload
      if (!frameId || !dataUri) break
      const node = figma.getNodeById(frameId)
      if (!node || node.type !== 'FRAME') break

      const base64Match = dataUri.match(/^data:image\/png;base64,(.+)$/)
      if (!base64Match) break

      const bytes = base64ToBytes(base64Match[1])

      const image = figma.createImage(bytes)
      node.fills = [{ type: 'IMAGE', imageHash: image.hash, scaleMode: 'FILL' }]
      figma.notify('Frame updated with re-rendered image')
      break
    }
    case 'GET_SELECTED_FRAME_META': {
      const selection = figma.currentPage.selection
      if (selection.length === 0) {
        postToUi({ type: 'ERROR', message: 'No frame selected. Select a Tasbir-generated frame first.' })
        break
      }
      const node = selection[0]
      if (node.type !== 'FRAME') {
        postToUi({ type: 'ERROR', message: 'Selected node is not a frame.' })
        break
      }
      const metaStr = node.getPluginData('tasbir')
      if (!metaStr) {
        postToUi({ type: 'ERROR', message: 'Selected frame was not generated by Tasbir. No metadata found.' })
        break
      }
      try {
        const meta = JSON.parse(metaStr)
        postToUi({ type: 'SETTINGS_LOADED', settings: { frameMeta: meta, frameId: node.id } })
      } catch {
        postToUi({ type: 'ERROR', message: 'Corrupted frame metadata.' })
      }
      break
    }
    case 'UPDATE_FRAME_META': {
      const { frameId, key, value } = msg.payload
      if (!frameId) break
      const node = figma.getNodeById(frameId)
      if (!node) break
      const metaStr = node.getPluginData('tasbir')
      if (!metaStr) break
      try {
        const meta = JSON.parse(metaStr)
        meta[key] = value
        node.setPluginData('tasbir', JSON.stringify(meta))
      } catch {}
      break
    }
    case 'SAVE_SETTINGS': {
      if (msg.payload?.apiBaseUrl) {
        apiBaseUrl = msg.payload.apiBaseUrl
        await figma.clientStorage.setAsync('tasbir-api-base-url', apiBaseUrl)
      }
      if (msg.payload?.apiKey !== undefined) {
        apiKey = msg.payload.apiKey
        await figma.clientStorage.setAsync('tasbir-api-key', apiKey)
      }
      figma.notify('Settings saved')
      break
    }
    case 'GET_SETTINGS': {
      await loadSettings()
      postToUi({ type: 'SETTINGS_LOADED', settings: { apiBaseUrl, apiKey } })
      break
    }
    case 'CREATE_TOKEN_VARIABLES': {
      const tokens = msg.payload
      if (!tokens?.colors) break

      try {
        const collection = figma.variables.createVariableCollection('Tasbir Design Tokens')
        const group = collection.addMode('Default')
        const modeId = collection.modes[0]?.modeId
        if (!modeId) break

        function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
          const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex)
          if (!m) return null
          return { r: parseInt(m[1], 16) / 255, g: parseInt(m[2], 16) / 255, b: parseInt(m[3], 16) / 255 }
        }

        const created: string[] = []
        for (const [groupName, colorGroup] of Object.entries(tokens.colors as Record<string, any>)) {
          if (typeof colorGroup !== 'object') continue
          for (const [shade, hex] of Object.entries(colorGroup)) {
            if (typeof hex !== 'string' || !hex.startsWith('#')) continue
            const rgb = hexToRgb(hex)
            if (!rgb) continue
            const variable = figma.variables.createVariable(`tasbir/${groupName}/${shade}`, collection.id, 'COLOR')
            variable.setValueForMode(modeId, rgb)
            created.push(`tasbir/${groupName}/${shade}`)
          }
        }
        figma.notify(`Created ${created.length} color variables`)
      } catch (e: any) {
        figma.notify(`Token sync failed: ${e.message}`, { error: true })
      }
      break
    }
  }
}

loadSettings()
