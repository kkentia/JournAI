import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { map } from 'rxjs/operators';

export const userSetupGuard: CanActivateFn = () => {
  const http = inject(HttpClient);
  const router = inject(Router);

  return http.get<any>('http://localhost:8000/UserData').pipe(
    map(data => {
      const hasData = data && data.age && data.gender;
      if (!hasData) {
        return router.createUrlTree(['/homepage']);
      }
      return true;
    })
  );
};
