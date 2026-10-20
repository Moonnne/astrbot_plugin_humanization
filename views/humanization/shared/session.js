export function sessionLabel(umo, name) {
  const [platform,kind,...parts] = umo.split(':');
  const id = parts.join(':');
  const label = name && name !== umo ? name : id;
  return `${platform} · ${kind === 'GroupMessage' ? '群聊' : '私聊'} · ${label}`;
}
