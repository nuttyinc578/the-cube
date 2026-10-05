"""Independent 2D convex collision solver. No Pymunk or Chipmunk dependency.

Fixed-step integration, SAT contacts, rotational impulses and Coulomb friction.
Only the subset of the body/shape API used by CPE is provided.
"""
from __future__ import annotations
import math
from types import SimpleNamespace


class Vec2d:
    __slots__ = ('x', 'y')
    def __init__(self, x=0, y=0): self.x, self.y = float(x), float(y)
    def __iter__(self): return iter((self.x, self.y))
    def __getitem__(self, i): return (self.x, self.y)[i]
    def __add__(self, other): return Vec2d(self.x+other[0], self.y+other[1])
    def __sub__(self, other): return Vec2d(self.x-other[0], self.y-other[1])
    def __mul__(self, n): return Vec2d(self.x*n, self.y*n)
    __rmul__ = __mul__
    def __truediv__(self, n): return self*(1/n)
    def __neg__(self): return self*-1
    @property
    def length(self): return math.hypot(self.x, self.y)
    def normalized(self): return self/self.length if self.length else Vec2d()
    def dot(self, v): return self.x*v[0]+self.y*v[1]
    def cross(self, v): return self.x*v[1]-self.y*v[0]


def vector(v): return v if isinstance(v, Vec2d) else Vec2d(*v)
def moment_for_circle(mass, inner, outer): return mass*(inner*inner+outer*outer)/2
def moment_for_poly(mass, vertices):
    numerator = denominator = 0.0
    points = [vector(v) for v in vertices]
    for a, b in zip(points, points[1:]+points[:1]):
        weight = abs(a.cross(b))
        numerator += weight*(a.dot(a)+a.dot(b)+b.dot(b))
        denominator += weight
    return mass*numerator/(6*denominator) if denominator else mass


class Body:
    def __init__(self, mass=0, moment=0):
        self.mass, self.moment = float(mass), float(moment)
        self._position, self._velocity = Vec2d(), Vec2d()
        self.angle = self.angular_velocity = self.torque = 0.0
        self.force = Vec2d()
    @property
    def position(self): return self._position
    @position.setter
    def position(self, value): self._position = vector(value)
    @property
    def velocity(self): return self._velocity
    @velocity.setter
    def velocity(self, value): self._velocity = vector(value)
    @property
    def inverse_mass(self): return 1/self.mass if self.mass else 0
    @property
    def inverse_moment(self): return 1/self.moment if self.moment else 0
    def activate(self): pass
    def rotate(self, point):
        p = vector(point); c, s = math.cos(self.angle), math.sin(self.angle)
        return Vec2d(c*p.x-s*p.y, s*p.x+c*p.y)
    def local_to_world(self, point): return self.position+self.rotate(point)
    def apply_impulse_at_world_point(self, impulse, point):
        j = vector(impulse)
        self.velocity += j*self.inverse_mass
        self.angular_velocity += (vector(point)-self.position).cross(j)*self.inverse_moment
    def apply_impulse_at_local_point(self, impulse, point=(0, 0)):
        self.apply_impulse_at_world_point(self.rotate(impulse), self.local_to_world(point))
    def apply_force_at_world_point(self, force, point):
        f = vector(force); self.force += f
        self.torque += (vector(point)-self.position).cross(f)
    def apply_force_at_local_point(self, force, point=(0, 0)):
        self.apply_force_at_world_point(self.rotate(force), self.local_to_world(point))


class Shape:
    def __init__(self, body):
        self.body = body
        self.friction, self.elasticity, self.collision_type = .72, .48, 0


class Circle(Shape):
    def __init__(self, body, radius): super().__init__(body); self.radius = float(radius)
    def point_query(self, point): return SimpleNamespace(distance=(vector(point)-self.body.position).length-self.radius)


class Poly(Shape):
    def __init__(self, body, vertices):
        super().__init__(body); self.vertices = [vector(v) for v in vertices]
    def get_vertices(self): return self.vertices
    def world_vertices(self): return [self.body.local_to_world(v) for v in self.vertices]
    def point_query(self, point):
        p, vertices = vector(point), self.world_vertices()
        signs, distance = [], float('inf')
        for a, b in zip(vertices, vertices[1:]+vertices[:1]):
            edge = b-a; signs.append(edge.cross(p-a))
            t = max(0, min(1, (p-a).dot(edge)/max(1e-12, edge.dot(edge))))
            distance = min(distance, (p-(a+edge*t)).length)
        inside = all(s >= 0 for s in signs) or all(s <= 0 for s in signs)
        return SimpleNamespace(distance=-distance if inside else distance)


class Segment(Shape):
    def __init__(self, body, a, b, radius):
        super().__init__(body); self.a, self.b, self.radius = vector(a), vector(b), radius


def projection(shape, axis):
    if isinstance(shape, Circle):
        mid = shape.body.position.dot(axis); return mid-shape.radius, mid+shape.radius
    values = [p.dot(axis) for p in shape.world_vertices()]
    return min(values), max(values)


def contact(a, b):
    if isinstance(a, Circle) and isinstance(b, Circle):
        delta = b.body.position-a.body.position
        depth = a.radius+b.radius-delta.length
        normal = delta.normalized() if delta.length else Vec2d(1, 0)
        return (normal, depth, a.body.position+normal*a.radius) if depth > 0 else None
    axes = []
    for shape in (a, b):
        if isinstance(shape, Poly):
            vertices = shape.world_vertices()
            for p, q in zip(vertices, vertices[1:]+vertices[:1]):
                edge = q-p
                if edge.length: axes.append(Vec2d(-edge.y, edge.x).normalized())
    if isinstance(a, Circle) or isinstance(b, Circle):
        circle, poly = (a, b) if isinstance(a, Circle) else (b, a)
        closest = min(poly.world_vertices(), key=lambda p: (p-circle.body.position).length)
        delta = closest-circle.body.position
        if delta.length: axes.append(delta.normalized())
    depth, normal = float('inf'), None
    for axis in axes:
        lo_a, hi_a = projection(a, axis); lo_b, hi_b = projection(b, axis)
        overlap = min(hi_a-lo_b, hi_b-lo_a)
        if overlap <= 0: return None
        if overlap < depth: depth, normal = overlap, axis
    if normal is None: return None
    if (b.body.position-a.body.position).dot(normal) < 0: normal = -normal
    def support(shape, axis):
        if isinstance(shape, Circle): return shape.body.position+axis*shape.radius
        vertices = shape.world_vertices(); maximum = max(p.dot(axis) for p in vertices)
        selected = [p for p in vertices if maximum-p.dot(axis) < .001]
        return sum(selected, Vec2d())/len(selected)
    return normal, depth, (support(a, normal)+support(b, -normal))*.5


class Space:
    def __init__(self):
        self.static_body = Body(); self.shapes, self.bodies = [], []
        self._gravity = Vec2d(0, 900); self.iterations = 8; self.callback = None
    @property
    def gravity(self): return self._gravity
    @gravity.setter
    def gravity(self, value): self._gravity = vector(value)
    def add(self, *items):
        for item in items:
            collection = self.bodies if isinstance(item, Body) else self.shapes
            if item not in collection: collection.append(item)
    def remove(self, *items):
        for item in items:
            collection = self.bodies if isinstance(item, Body) else self.shapes
            if item in collection: collection.remove(item)
    def on_collision(self, *types, post_solve=None): self.callback = post_solve
    def _resolve(self, a, b, normal, depth, point):
        first, second = a.body, b.body
        inv = first.inverse_mass+second.inverse_mass
        if not inv: return
        correction = normal*(max(0, depth-.02)*.75/inv)
        first.position -= correction*first.inverse_mass
        second.position += correction*second.inverse_mass
        ra, rb = point-first.position, point-second.position
        def speed(body, arm): return body.velocity+Vec2d(-arm.y, arm.x)*body.angular_velocity
        relative = speed(second, rb)-speed(first, ra)
        closing = relative.dot(normal)
        if closing >= 0: return
        effective = inv+ra.cross(normal)**2*first.inverse_moment+rb.cross(normal)**2*second.inverse_moment
        magnitude = -(1+min(a.elasticity, b.elasticity))*closing/effective
        impulse = normal*magnitude
        first.apply_impulse_at_world_point(-impulse, point)
        second.apply_impulse_at_world_point(impulse, point)
        tangent = relative-normal*closing
        if tangent.length:
            tangent = tangent.normalized()
            denominator = inv+ra.cross(tangent)**2*first.inverse_moment+rb.cross(tangent)**2*second.inverse_moment
            friction = -relative.dot(tangent)/denominator
            limit = magnitude*math.sqrt(max(0, a.friction*b.friction))
            j = tangent*max(-limit, min(limit, friction))
            first.apply_impulse_at_world_point(-j, point); second.apply_impulse_at_world_point(j, point)
        if self.callback:
            arbiter = SimpleNamespace(total_impulse=impulse, shapes=(a, b), contact_point_set=SimpleNamespace(points=[SimpleNamespace(point_a=point)]))
            self.callback(arbiter, self, None)
    def step(self, dt):
        for body in self.bodies:
            if body.mass:
                body.velocity += (self.gravity+body.force*body.inverse_mass)*dt
                body.angular_velocity += body.torque*body.inverse_moment*dt
                body.position += body.velocity*dt; body.angle += body.angular_velocity*dt
                body.force, body.torque = Vec2d(), 0.0
        dynamic = [s for s in self.shapes if not isinstance(s, Segment)]
        boundaries = [s for s in self.shapes if isinstance(s, Segment)]
        for _ in range(min(self.iterations, 8)):
            for shape in dynamic:
                for wall in boundaries:
                    edge = wall.b-wall.a; normal = Vec2d(-edge.y, edge.x).normalized()
                    # Orient each boundary toward the world interior (CPE walls).
                    if abs(edge.x) > abs(edge.y): normal = Vec2d(0, -1)
                    elif wall.a.x > 10: normal = Vec2d(-1, 0)
                    else: normal = Vec2d(1, 0)
                    low, _ = projection(shape, normal)
                    depth = wall.a.dot(normal)+wall.radius-low
                    if depth > 0:
                        p = shape.body.position-normal*(shape.radius if isinstance(shape, Circle) else max(0, shape.body.position.dot(normal)-low))
                        self._resolve(wall, shape, normal, depth, p)
            ordered = sorted(dynamic, key=lambda s: projection(s, Vec2d(1, 0))[0])
            for i, a in enumerate(ordered):
                _, high = projection(a, Vec2d(1, 0))
                for b in ordered[i+1:]:
                    if projection(b, Vec2d(1, 0))[0] > high: break
                    hit = contact(a, b)
                    if hit: self._resolve(a, b, *hit)
