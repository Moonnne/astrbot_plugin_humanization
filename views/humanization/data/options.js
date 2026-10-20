export const outcomes = [
  ['pending','待执行'], ['processed','发送流程完成'], ['observed','保持沉默'],
  ['failed','失败'], ['superseded','已被取代'], ['unconfirmed','结果未确认'],
].map(([value,title]) => ({value,title}));

export const emotions = [
  ['NEUTRAL','平静'], ['JOY','高兴'], ['AFFECTION','亲近'], ['PRIDE','自豪'],
  ['ANTICIPATION','期待'], ['SURPRISE','惊讶'], ['UNCERTAINTY','不确定'],
  ['SADNESS','难过'], ['ANGER','生气'], ['AVERSION','反感'], ['FEAR','害怕'],
  ['SELF_CONSCIOUS','难为情'], ['LOW_ENERGY','低落／疲倦'], ['ENVY','羡慕'],
].map(([value,title]) => ({value,title}));
