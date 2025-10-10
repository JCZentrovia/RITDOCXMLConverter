import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { map } from 'rxjs/operators';

export const adminGuard = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.currentUser$.pipe(
    map(user => {
      if (user && authService.isAdmin()) {
        return true;
      } else {
        // Redirect to dashboard if not admin
        router.navigate(['/dashboard']);
        return false;
      }
    })
  );
};
