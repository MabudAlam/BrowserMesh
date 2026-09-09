declare module "@novnc/novnc/core/rfb.js" {
  export interface RFBOptions {
    wsProtocols?: string[]
    credentials?: { password?: string }
    local_cursor?: boolean
    scaleViewport?: boolean
    resizeSession?: boolean
    showDotCursor?: boolean
    viewOnly?: boolean
  }
  export default class RFB {
    constructor(container: HTMLElement, url: string, options?: RFBOptions)
    scaleViewport: boolean
    resizeSession: boolean
    showDotCursor: boolean
    viewOnly: boolean
    disconnect(): void
    connect(): void
    sendCtrlAltDel(): void
    clipboardPasteFrom(text: string): void
    addEventListener(event: string, handler: (e: any) => void): void
    removeEventListener(event: string, handler: (e: any) => void): void
  }
}
