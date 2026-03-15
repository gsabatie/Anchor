import { useState, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import './TextInput.css'

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
    </svg>
  )
}

export default function TextInput({ onSend, disabled }) {
  const { t } = useTranslation()
  const [value, setValue] = useState('')
  const inputRef = useRef(null)

  const handleSubmit = useCallback((e) => {
    e.preventDefault()
    const text = value.trim()
    if (!text || disabled) return
    onSend(text)
    setValue('')
    inputRef.current?.focus()
  }, [value, disabled, onSend])

  return (
    <form className="text-input" onSubmit={handleSubmit}>
      <input
        ref={inputRef}
        className="text-input__field"
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={t('textInputPlaceholder')}
        disabled={disabled}
        autoComplete="off"
      />
      <button
        className="text-input__btn"
        type="submit"
        disabled={disabled || !value.trim()}
        aria-label={t('textInputSend')}
      >
        <SendIcon />
      </button>
    </form>
  )
}
