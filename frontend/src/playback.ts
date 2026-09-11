export function vehiclePhase(elapsed:number,departure:number,duration:number,engine:boolean){
 const travel=(elapsed-departure)/duration;
 if(travel<0)return {visible:false,returning:false,fraction:0};
 if(engine){const cycle=travel%2;return {visible:true,returning:cycle>=1,fraction:cycle%1}}
 // New exercise traffic waves enter the same route, separated by a short gap.
 const cycle=travel%1.18;return {visible:cycle<=1,returning:false,fraction:Math.min(cycle,1)};
}
