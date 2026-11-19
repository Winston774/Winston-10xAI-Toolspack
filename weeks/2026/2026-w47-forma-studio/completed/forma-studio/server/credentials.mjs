import path from 'node:path'
import { spawnSync } from 'node:child_process'

const keyNames = ['openaiKey','fishApiKey','breezeToken']
export function takeSecrets(value) {
  return Object.fromEntries(keyNames.map(key=>[key,value[key] || '']))
}
export function withoutSecrets(value) {
  return Object.fromEntries(Object.entries(value).filter(([key])=>!keyNames.includes(key)))
}
const encrypt = '[System.Security.Cryptography.ProtectedData]::Protect($bytes,$null,[System.Security.Cryptography.DataProtectionScope]::CurrentUser)'
const decrypt = '[System.Security.Cryptography.ProtectedData]::Unprotect($bytes,$null,[System.Security.Cryptography.DataProtectionScope]::CurrentUser)'

// The command contains only static code. The UTF-8 payload and result both travel as base64 on private pipes.
function dpapi(input, operation) {
  const script = "$ErrorActionPreference='Stop'\nAdd-Type -AssemblyName System.Security\n" +
    "$bytes=[Convert]::FromBase64String([Console]::In.ReadToEnd())\n$result=" + operation +
    "\n[Console]::Out.Write([Convert]::ToBase64String($result))"
  const executable=path.join(process.env.SystemRoot || 'C:\\Windows','System32','WindowsPowerShell','v1.0','powershell.exe')
  const run=spawnSync(executable,['-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',Buffer.from(script,'utf16le').toString('base64')],{
    input,encoding:'utf8',stdio:['pipe','pipe','pipe'],windowsHide:true,shell:false,timeout:15000,maxBuffer:128*1024,
  })
  if (run.status!==0 || !/^[A-Za-z0-9+/]+={0,2}$/.test(run.stdout || '')) {
    throw Error('Windows 無法保護或讀取金鑰，請使用原本的 Windows 帳戶。已儲存設定會保留。')
  }
  return run.stdout
}
export function protect(secrets) {
  return dpapi(Buffer.from(JSON.stringify(secrets),'utf8').toString('base64'),encrypt)
}
export function unprotect(ciphertext) {
  const value=JSON.parse(Buffer.from(dpapi(ciphertext,decrypt),'base64').toString('utf8'))
  if(!keyNames.every(key=>typeof value[key]==='string'))throw Error('金鑰資料格式無效。')
  return takeSecrets(value)
}
