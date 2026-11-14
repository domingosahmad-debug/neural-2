(async()=>{
  const proof={};const $=id=>document.getElementById('executive-'+id);
  const wait=async test=>{for(let i=0;i<120;i++){if(test())return;await new Promise(r=>setTimeout(r,30));}throw new Error('Executive UI state did not arrive');};
  await wait(()=>typeof token==='string'&&Object.keys(workspace).length>0);
  const created=await api('project',{name:'Executive verification · no model calls',brief:'Test optional one-pass planning only.'});selectProject(created.id);
  $('open').click();proof.dialogOpens=document.getElementById('executive-dialog').open;proof.defaultOff=$('create').disabled;
  $('toggle').click();await wait(()=>$('toggle').textContent==='Disable station');proof.manualEnable=!$('create').disabled;
  $('model').value='Astra / Fable custom';$('task').value='Allocate one Director task. Verify capabilities and quota; return once and stop.';
  // Exercise real form submission while capturing its downloaded packet locally.
  const realDownload=download;let packet;download=p=>{packet=p;};try{$('form').requestSubmit();await wait(()=>!!packet);}finally{download=realDownload;}
  proof.customModelPacket=packet.model==='Astra / Fable custom';proof.planningOnly=packet.authority.includes('Do not edit media');proof.quotaHonest=packet.availability.quota.startsWith('UNKNOWN');
  await api('result',{...packet.resultTemplate,summary:'One brief pass to Director; then stop.',allocationPlan:[{station:'Director',model:'Fixture director',task:'Freeze the brief.',acceptance:'Human scope recorded.',dependsOn:[],availabilityEvidence:'Synthetic test only; no provider executed.'}]});render();
  proof.resultVisible=$('result').textContent.includes('Freeze the brief.');
  [...$('result').querySelectorAll('button')].find(b=>b.textContent==='Approve plan evidence').click();await wait(()=>$('result').textContent.includes('Apply plan'));
  [...$('result').querySelectorAll('button')].find(b=>b.textContent.startsWith('Apply plan')).click();await wait(()=>$('result').textContent.includes('Plan handed off.'));
  proof.appliesOneHandoff=Object.values(project().assignments).filter(r=>r.station==='Director').length===1;
  $('toggle').click();await wait(()=>$('toggle').textContent==='Enable station');proof.manuallyDisabled=$('create').disabled;
  $('close').click();proof.dialogCloses=!document.getElementById('executive-dialog').open;
  // Keep the user on the Editor fixture; optional station remains off there and on the real project.
  const editing=Object.values(workspace).filter(p=>p.name==='Editor verification · synthetic media').at(-1);if(editing){selectProject(editing.id);document.querySelector('#edit-tab').click();}
  return proof;
})()
