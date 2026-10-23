const SIGNAL_SESSION_MESSAGES = new Set(['Closing session:', 'Opening session:'])

export function installSignalSessionLogFilter(consoleObject = console) {
  const info = consoleObject.info.bind(consoleObject)
  // shortcut: libsignal 6 dumps key material with console.info; remove when upstream stops doing so.
  consoleObject.info = (...args) => {
    if (!SIGNAL_SESSION_MESSAGES.has(args[0])) info(...args)
  }
}
