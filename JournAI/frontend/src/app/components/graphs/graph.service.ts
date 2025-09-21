import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

export type GraphView = 'day' | 'week' | 'month';


export interface GraphFilter {
  entryId?: number;
  sessionId?: number;
}

@Injectable({
  providedIn: 'root'
})
export class GraphService {

  public selectedViewSubject = new BehaviorSubject<GraphView>('day');
  public selectedView$: Observable<GraphView> = this.selectedViewSubject.asObservable();

  private filterSubject = new BehaviorSubject<GraphFilter>({});
  public filter$: Observable<GraphFilter> = this.filterSubject.asObservable();

  //setter
  public setView(view: GraphView): void {
    this.selectedViewSubject.next(view);
  }

 //getter
  public getCurrentView(): GraphView {
    return this.selectedViewSubject.getValue();
  }
  
  public setFilter(filter: GraphFilter): void { //for when we have something like http://localhost:4200/graphs?entry_id=18
    this.filterSubject.next(filter);
  }

  public getCurrentFilter(): GraphFilter {
    return this.filterSubject.getValue();
  }
}
