import {element} from './client.js';

function block(target,className,content) {
  const node=element('div',content,{class:className});
  target.append(node);
  return node;
}

function strip(target,label,value,max,display) {
  const row=block(target,'scale-entry'); block(row,'scale-label',label);
  const ruler=block(row,'scale-rule'); const fill=block(ruler,'fill');
  fill.style.width=`${Math.min(100,100*value/Math.max(1,max))}%`;
  block(row,'scale-readout',display);
}

export function visualize(report,selected) {
  const target=document.querySelector('#visual');
  target.replaceChildren();
  const measurement=report.cases?.find(row=>row.case===selected)?.measure;
  if (!measurement) {block(target,'chart-note','选择有计算值的分组');return;}
  const e=measurement.evidence;

  for (const [ticket,load] of Object.entries(e.loads)) {
    const stack=block(target,'weight-stack',`磅单 ${ticket}`);
    for(const [name,grams] of [['净重',load.net_g],['干重',load.dry_g],['结算',load.payable_g]]) {
      strip(stack,name,grams,load.net_g,`${grams.toLocaleString()} g`);
    }
  }
}
